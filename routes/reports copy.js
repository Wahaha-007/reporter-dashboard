// Date : 25 Sep 24
// Purpose : To have NodeJS as Backend
// To Run it
// Step 1 : Run Local Dynamo
// 		java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -dbPath ./dynamodb_data
// -- Test--
//		aws dynamodb scan --table-name Report --endpoint-url http://localhost:8000
// 		aws dynamodb scan --table-name ReportAck --endpoint-url http://localhost:8000
// 		curl -X GET http://localhost:3000/api/reports/stats
//
//    
// Step 2 : Run API Server
//	  nodemon app.js
// Step 3 : See the web at
// 		http://localhost:3000/dashboard/remaining


const express = require('express');
const AWS = require('aws-sdk');
const router = express.Router();

// Initialize DynamoDB DocumentClient
const dynamodb = new AWS.DynamoDB.DocumentClient({
	endpoint: process.env.DYNAMODB_ENDPOINT,
	region: 'ap-southeast-1' // ต้องมี ไม่มีจะ Error
});

// ================================ GET Route ============================== //

// Get all reports
router.get('/', async (req, res) => {
	const params = {
		TableName: 'Report'
	};

	try {
		const data = await dynamodb.scan(params).promise();
		res.status(200).json(data.Items);
	} catch (error) {
		// console.log('Error loading reports:', error);
		res.status(500).json({ error: 'Could not load reports' });
	}
});

// ================================ Dashboard #1 Route ============================== //
// เอาพวก Get มาอยู่ด้วยกันก่อนและจะได้เหมือนไล่ทำ if then else ทีละ step ให้ถูก เพราะ Algorithm 
// ในการหา route มันเป็น แบบ String compare พวก *.* อะไรทำนองนี้ต้องไว้หลังสุด

// Utility function to count reports by department in a specific table
async function countReports(tableName, department) {
	const params = {
		TableName: tableName,
		FilterExpression: '#dept = :department',
		ExpressionAttributeNames: { '#dept': 'department' },
		ExpressionAttributeValues: { ':department': department }
	};

	const data = await dynamodb.scan(params).promise();
	return data.Count;
}

// Route to get report stats (for the chart)
// Route to get report stats (for the chart)
router.get('/stats', async (req, res) => {
	try {
		const departments = ['HR', 'Facility', 'Production', 'Finance', 'Maintenance'];
		const statuses = ['Report', 'Ack', 'Processing', 'Done'];

		let reportCounts = {
			Report: [],
			Ack: [],
			Processing: [],
			Done: []
		};

		for (let department of departments) {
			for (let status of statuses) {
				const params = {
					TableName: 'Report',
					IndexName: 'StatusIndex',  // Use the GSI we created
					KeyConditionExpression: '#status = :status',
					FilterExpression: 'department = :department',
					ExpressionAttributeNames: {
						'#status': 'status'  // Alias to handle reserved keyword
					},
					ExpressionAttributeValues: {
						':status': status,
						':department': department
					}
				};

				const data = await dynamodb.query(params).promise();
				reportCounts[status].push(data.Count);
			}
		}

		console.log("reportCounts:", reportCounts);
		res.json({
			departments,
			reportCounts: reportCounts.Report,
			ackCounts: reportCounts.Ack,
			processingCounts: reportCounts.Processing,
			doneCounts: reportCounts.Done
		});
	} catch (err) {
		console.error(err);
		res.status(500).json({ error: 'Could not load report stats' });
	}
});

// Route to get detailed report data (for the table)
router.get('/details', async (req, res) => {
	const { department, status } = req.query;

	try {
		const params = {
			TableName: 'Report',
			IndexName: 'StatusIndex',
			KeyConditionExpression: '#status = :status',
			FilterExpression: 'department = :department',
			ExpressionAttributeNames: {
				'#status': 'status'  // Alias for reserved keyword
			},
			ExpressionAttributeValues: {
				':status': status,
				':department': department
			}
		};

		const gsiData = await dynamodb.query(params).promise();

		// Now, use the report_id from the GSI result to get the full item from the main table
		const fullItems = await Promise.all(
			gsiData.Items.map(async (item) => {
				const fullParams = {
					TableName: 'Report',
					Key: { report_id: item.report_id }  // ใจความสำคัญคือตรงนี้เลย
				};
				const fullData = await dynamodb.get(fullParams).promise();
				return fullData.Item;
			})
		);

		// Send the fully populated items back as a response
		res.json(fullItems);
	} catch (err) {
		console.error(err);
		res.status(500).json({ error: 'Could not load report details' });
	}
});

const getStatusChangeTimes = () => {
	return {
		"HR": [2, 4, 6],
		"Facility": [1, 5, 3],
		"Production": [4, 3, 2],
		"Finance": [5, 2, 1],
		"Maintenance": [1, 6, 0]
	};
};

router.get('/status-change-times', (req, res) => {
	const data = getStatusChangeTimes();  // You will replace this with actual DynamoDB data fetching
	res.json(data);
});














// ---------------------------------------------------------------------------------- //

// Get a report by ID
router.get('/:report_id', async (req, res) => {
	const report_id = req.params.report_id;
	const params = {
		TableName: 'Report',
		Key: {
			report_id: report_id
		}
	};

	try {
		const data = await dynamodb.get(params).promise();
		if (data.Item) {
			res.status(200).json(data.Item);
		} else {
			res.status(404).json({ error: 'Report not found' });
		}
	} catch (error) {
		res.status(500).json({ error: 'Could not load report' });
	}
});

// ================================ POST Route ============================== //

// Create a new report
router.post('/', async (req, res) => {
	const { department, details, location, status, topic, username, createdAt } = req.body;
	const report_id = AWS.util.uuid.v4(); // Generate a unique report_id

	const params = {
		TableName: 'Report',
		Item: {
			report_id,
			department,
			details,
			location,
			status,
			topic,
			username,
			createdAt
		}
	};

	try {
		await dynamodb.put(params).promise();
		res.status(201).json({ message: 'Report created successfully', report_id });
	} catch (error) {
		res.status(500).json({ error: 'Could not create report' });
	}
});

// ================================ PUT Route ============================== //
// Update report status (e.g., Ack, Processing, Done)
router.put('/:report_id/status', async (req, res) => {
	const report_id = req.params.report_id;
	const { status, comment, createdAt, updater, updater_role } = req.body;

	let tableName;
	switch (status) {
		case 'Ack':
			tableName = 'ReportAck';
			break;
		case 'Processing':
			tableName = 'ReportProcessing';
			break;
		case 'Done':
			tableName = 'ReportDone';
			break;
		default:
			return res.status(400).json({ error: 'Invalid status' });
	}

	const params = {
		TableName: tableName,
		Item: {
			report_id,
			comment,
			createdAt,
			updater,
			updater_role
		}
	};

	try {
		await dynamodb.put(params).promise();
		res.status(200).json({ message: `Report status updated to ${status}` });
	} catch (error) {
		res.status(500).json({ error: 'Could not update report status' });
	}
});

module.exports = router;