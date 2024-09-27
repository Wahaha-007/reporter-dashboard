# Date : 27 Sep 24
# Purpose : To generate the mocking data for loca DynamoDB development, Unified Version
# (ก่อนอื่นดูที่มุมขวาล่างว่าใช้ Python 3.8.20 นะ)
# To Run
#					ไปที่ $ หรือกด <Ctrl-`>
#  				python3 GenMockDataU.py
# To Test
# 				aws dynamodb scan --table-name Report --endpoint-url http://localhost:8000


import boto3
from faker import Faker
from datetime import timedelta
import random

# Initialize Faker and DynamoDB client
fake = Faker()
dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")

def create_report_table():
	try:
		table = dynamodb.create_table(
				TableName='Report',
				KeySchema=[
					{
							'AttributeName': 'report_id',
							'KeyType': 'HASH'  # Partition key
					},
					{
					'AttributeName': 'createdAt',
					'KeyType': 'RANGE'  # Sort key
					}
				],
				AttributeDefinitions=[
					{
						'AttributeName': 'report_id',
						'AttributeType': 'S'
					},
					
        	{	'AttributeName': 'createdAt',
            'AttributeType': 'S'
        	},
					{
						'AttributeName': 'department',
						'AttributeType': 'S'  # Attribute for GSI
					}
				],
				ProvisionedThroughput={
						'ReadCapacityUnits': 5,
						'WriteCapacityUnits': 5
				},
				GlobalSecondaryIndexes=[
						{
								'IndexName': 'DepartmentIndex',
								'KeySchema': [
									{
										'AttributeName': 'department',
										'KeyType': 'HASH'  # Partition key for GSI
									},
                	{
                    'AttributeName': 'createdAt',
                    'KeyType': 'RANGE'  # Sort key for GSI
                	}
								],
								'Projection': {
									'ProjectionType': 'ALL'  # Include all attributes in the GSI projection
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
		print("Table 'Report' with GSI 'DepartmentIndex' created successfully.")

	except Exception as e:
		print(f"Error creating table: {e}")

# Function to generate time deltas between status updates
def generate_time_deltas():
	days = random.randint(1, 10)
	hours = random.randint(0, 23)
	minutes = random.randint(0, 59)
	return timedelta(days=days, hours=hours, minutes=minutes)

# Function to generate mock data based on the status counts specified
def generate_mock_data(report_count=5, ack_count=5, processing_count=5, done_count=5):
    
	table = dynamodb.Table('Report')
	departments = ["HR", "Facility", "Production", "Finance", "Maintenance"]
	statuses = ['Report', 'Ack', 'Processing', 'Done']
	
	total_count = report_count + ack_count + processing_count + done_count
	t_done = done_count
	t_processing = processing_count + done_count
	t_ack = ack_count + processing_count + done_count
	
	for _ in range(total_count):
		report_id = fake.uuid4()
		department = random.choice(departments)
		username = fake.email()
		topic = fake.sentence()
		details = fake.text()
		imageUrl = fake.image_url()

		createdAt = fake.date_time_this_month()

		# Generate time deltas for each stage
		ack_time = createdAt + generate_time_deltas()
		processing_time = ack_time + generate_time_deltas()
		done_time = processing_time + generate_time_deltas()

		# Add comments for each status update
		comments = []
		if t_ack > 0:
			comments.append({
				"status": "Ack",
				"comment": "Report acknowledged",
				"imageUrl": fake.image_url(),
				"updater": fake.email(),
				"updater_role": "admin",
				"createdAt": ack_time.strftime('%Y-%m-%dT%H:%M:%SZ')
			})
		t_ack -= 1

		if t_processing > 0:
			comments.append({
				"status": "Processing",
				"comment": "Processing started",
				"imageUrl": fake.image_url(),
				"updater": fake.email(),
				"updater_role": "technician",
				"createdAt": processing_time.strftime('%Y-%m-%dT%H:%M:%SZ')
			})
		t_processing -= 1

		if t_done > 0:
			comments.append({
				"status": "Done",
				"comment": "Issue resolved",
				"imageUrl": fake.image_url(),
				"updater": fake.email(),
				"updater_role": "supervisor",
				"createdAt": done_time.strftime('%Y-%m-%dT%H:%M:%SZ')
			})
		t_done -= 1

		# Determine final status
		if t_done >= 0:
			status = "Done"
		elif t_processing >= 0:
			status = "Processing"
		elif t_ack >= 0:
			status = "Ack"
		else:
			status = "Report"

		# Insert the report into the DynamoDB table
		table.put_item(
			Item={
				'report_id': report_id,
				'department': department,
				'details': details,
				'location': {
						'latitude': str(fake.latitude()),
						'longitude': str(fake.longitude())
				},
				'status': status,  # Final status as selected
				'topic': topic,
				'username': username,
				'createdAt': createdAt.strftime('%Y-%m-%dT%H:%M:%SZ'),
				'acknowledgedAt': ack_time.strftime('%Y-%m-%dT%H:%M:%SZ') if status in ['Ack', 'Processing', 'Done'] else None,
				'processingStartedAt': processing_time.strftime('%Y-%m-%dT%H:%M:%SZ') if status in ['Processing', 'Done'] else None,
				'doneAt': done_time.strftime('%Y-%m-%dT%H:%M:%SZ') if status == 'Done' else None,
				'imageUrl': imageUrl,
				'comments': comments
			}
		)

	print(f"{total_count} mock reports added to UnifiedReportTable")


# Main function to create tables and insert mock data
def main():
	# Create Tables
	create_report_table()
	# Insert Data
	generate_mock_data(report_count=30, ack_count=20, processing_count=20, done_count=20)

if __name__ == "__main__":
	main()