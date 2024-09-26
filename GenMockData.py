# Date : 25 Sep 24
# Purpose : To generate the mocking data for loca DynamoDB development
# (ก่อนอื่นดูที่มุมขวาล่างว่าใช้ Python 3.8.20 นะ)
# To Run
#					ไปที่ $ หรือกด <Ctrl-`>
#  				python3 GenMockData.py


import boto3
import uuid
from faker import Faker
from datetime import datetime, timedelta

# Initialize Faker
faker = Faker()

# Connect to local DynamoDB
dynamodb = boto3.resource('dynamodb', endpoint_url='http://localhost:8000', region_name='ap-southeast-1')

def create_report_table():
	try:
		table = dynamodb.create_table(
			TableName='Report',
			KeySchema=[
				{
					'AttributeName': 'report_id',
					'KeyType': 'HASH'  # Partition key
				}
			],
			AttributeDefinitions=[
				{
					'AttributeName': 'report_id',
					'AttributeType': 'S'  # String
				},
				{
					'AttributeName': 'status',
					'AttributeType': 'S'  # String, for GSI
				}
			],
			ProvisionedThroughput={
				'ReadCapacityUnits': 10,
				'WriteCapacityUnits': 10
			},
			GlobalSecondaryIndexes=[
				{
					'IndexName': 'StatusIndex',  # GSI name
					'KeySchema': [
						{
							'AttributeName': 'status',
							'KeyType': 'HASH'  # Partition key for GSI
						}
					],
					'Projection': {
						'ProjectionType': 'INCLUDE',
						'NonKeyAttributes': ['department']  # We need department for querying
					},
					'ProvisionedThroughput': {
						'ReadCapacityUnits': 5,
						'WriteCapacityUnits': 5
					}
				}
			]
		)

		# Wait until the table exists before returning
		table.meta.client.get_waiter('table_exists').wait(TableName='Report')
		print("Table 'Report' with GSI 'StatusIndex' created successfully.")

	except Exception as e:
		print(f"Error creating table: {e}")


# Create the 'Report' table
def create_report_table_old():
	try:
		table = dynamodb.create_table(
			TableName='Report',
			KeySchema=[
				{'AttributeName': 'report_id', 'KeyType': 'HASH'}
			],
			AttributeDefinitions=[
				{'AttributeName': 'report_id', 'AttributeType': 'S'}
			],
			ProvisionedThroughput={
				'ReadCapacityUnits': 10,
				'WriteCapacityUnits': 10
			}
		)
		table.wait_until_exists()
		print("Table 'Report' created successfully!")
	except Exception as e:
			print(f"Table creation failed: {e}")

# Create the 'ReportAck', 'ReportProcessing', 'ReportDone' tables
def create_status_table(table_name):
	try:
		table = dynamodb.create_table(
			TableName=table_name,
			KeySchema=[
				{'AttributeName': 'report_id', 'KeyType': 'HASH'}
			],
			AttributeDefinitions=[
				{'AttributeName': 'report_id', 'AttributeType': 'S'}
			],
			ProvisionedThroughput={
				'ReadCapacityUnits': 10,
				'WriteCapacityUnits': 10
			}
		)
		table.wait_until_exists()
		print(f"Table '{table_name}' created successfully!")
	except Exception as e:
		print(f"Table creation failed: {e}")

# Insert mock data into 'Report'
def insert_report_data(n):
	report_table = dynamodb.Table('Report')
	
	for _ in range(n):
		report_id = str(uuid.uuid4())
		department = faker.random_element(elements=("HR", "Facility", "Production", "Finance", "Maintenance"))
		details = faker.text()
		location = {
			"latitude": faker.latitude(),
			"longitude": faker.longitude()
		}
		topic = faker.sentence(nb_words=3)
		username = faker.email()
		createdAt = faker.date_time_this_year().isoformat()

		report_table.put_item(
			Item={
				'report_id': report_id,
				'department': department,
				'details': details,
				'imageUrl': '',
				'location': location,
				'status': 'Report',
				'topic': topic,
				'username': username,
				'createdAt': createdAt
			}
		)
	print(f"{n} records inserted into 'Report' table")

# Insert mock data into 'ReportAck', 'ReportProcessing', 'ReportDone'

def insert_status_data(table_name, n, previous_table_name):
	status_table = dynamodb.Table(table_name)
	report_table = dynamodb.Table('Report')
	previous_table = dynamodb.Table(previous_table_name)
	
	# Get all report_ids from the Previous table
	report_ids = previous_table.scan(ProjectionExpression='report_id')['Items']
	report_ids = [item['report_id'] for item in report_ids[:n]]  # Limit to n records
	
	for report_id in report_ids:
		# Fetch the report details to get department and previous createdAt
		report_data = report_table.get_item(Key={'report_id': report_id})['Item']
		department = report_data['department']
	
		# Fetch the previous createdAt value

		previous_data = previous_table.get_item(Key={'report_id': report_id})['Item']
		previous_created_at = datetime.fromisoformat(previous_data['createdAt'])
		# Add a random interval (1-20 days) for this status step
		createdAt = previous_created_at + timedelta(days=faker.random_int(min=1, max=20))
	
		# Insert the status data with updated department and createdAt
		status_table.put_item(
			Item={
				'report_id': report_id,
				'comment': faker.text(max_nb_chars=100),
				'createdAt': createdAt.isoformat(),
				'imageUrl': '',
				'updater': faker.email(),
				'updater_role': f"{department}-Worker",
				'department': department
			}
		)
	print(f"{n} records inserted into '{table_name}' table")

# Function to update the 'status' of each report in the 'Report' table
def update_report_status():
	i = 0
	report_table = dynamodb.Table('Report')
	ack_table = dynamodb.Table('ReportAck')
	processing_table = dynamodb.Table('ReportProcessing')
	done_table = dynamodb.Table('ReportDone')

	# Step 1: Scan the 'Report' table to get all reports
	response = report_table.scan()
	reports = response['Items']

	for report in reports:
		report_id = report['report_id']
		new_status = 'Report'  # Default status

		# Step 2: Check if report_id is in the 'ReportDone' table
		done_response = done_table.get_item(Key={'report_id': report_id})
		if 'Item' in done_response:
			new_status = 'Done'

		# Step 3: Check if report_id is in the 'ReportProcessing' table (if not already 'Done')
		elif new_status != 'Done':
			processing_response = processing_table.get_item(Key={'report_id': report_id})
			if 'Item' in processing_response:
				new_status = 'Processing'

		# Step 4: Check if report_id is in the 'ReportAck' table (if not already 'Processing' or 'Done')
			elif new_status != 'Processing':
				ack_response = ack_table.get_item(Key={'report_id': report_id})
				if 'Item' in ack_response:
					new_status = 'Ack'

		# Step 5: Update the 'status' in the 'Report' table
		if report['status'] != new_status:  # Only update if status has changed
			report_table.update_item(
				Key={'report_id': report_id},
				UpdateExpression='SET #status = :new_status',
				ExpressionAttributeNames={'#status': 'status'},
				ExpressionAttributeValues={':new_status': new_status}
			)
			print(f"Updated report_id: {report_id} to status: {new_status}",i)
			i+=1

# Main function to create tables and insert mock data
def main():
	# Create Tables
	create_report_table()
	create_status_table('ReportAck')
	create_status_table('ReportProcessing')
	create_status_table('ReportDone')

	# Insert Data
	insert_report_data(50)              # 50 records in 'Report'
	insert_status_data('ReportAck', 40, previous_table_name='Report') # Ack after Report
	insert_status_data('ReportProcessing', 20, previous_table_name='ReportAck') # Processing after Ack
	insert_status_data('ReportDone', 10, previous_table_name='ReportProcessing') # Done after Processing

	# Call the function to update the statuses
	update_report_status()

if __name__ == "__main__":
	main()
