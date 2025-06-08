import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Get backend API URL from environment variable
const BACKEND_API_URL = import.meta.env.BACKEND_API_URL || 'http://localhost:8000/api';

// GET handler for retrieving all meetings
export const GET: RequestHandler = async ({ fetch }) => {
	try {
		const response = await fetch(`${BACKEND_API_URL}/meetings/`);
		
		if (!response.ok) {
			const errorData = await response.json();
			throw error(response.status, errorData.detail || 'Failed to get meetings');
		}
		
		const meetings = await response.json();
		return json(meetings);
	} catch (err) {
		console.error('Error fetching meetings:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};

// POST handler for creating a new meeting
export const POST: RequestHandler = async ({ request, fetch }) => {
	try {
		const meetingData = await request.json();
		
		const response = await fetch(`${BACKEND_API_URL}/meetings/`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(meetingData)
		});
		
		if (!response.ok) {
			const errorData = await response.json();
			throw error(response.status, errorData.detail || 'Failed to create meeting');
		}
		
		const meeting = await response.json();
		return json(meeting);
	} catch (err) {
		console.error('Error creating meeting:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};