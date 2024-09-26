// Date : 25 Sep 24
// Purpose : To have NodeJS as Backend

require('dotenv').config();
const express = require('express');
const path = require('path');
const reportsRouter = require('./routes/reports');
const app = express();

app.use(express.json());

// Serve static files from 'public' directory
app.use(express.static('public'));

// Routes
app.use('/api/reports', reportsRouter);

// Dashboard route
app.get('/dashboard/remaining', (req, res) => {
	res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

// Start the server
const port = process.env.PORT || 3000;
app.listen(port, () => {
	console.log(`Server running on port ${port}`);
});
