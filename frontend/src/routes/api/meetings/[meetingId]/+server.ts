import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Get backend API URL from environment variable
const BACKEND_API_URL = import.meta.env.BACKEND_API_URL || 'http://localhost:8000/api';

// GET handler for retrieving a specific meeting
export const GET: RequestHandler = async ({ params, fetch }) => {
	try {
		const { meetingId } = params;
		const response = await fetch(`${BACKEND_API_URL}/meetings/${meetingId}`);
		
		if (!response.ok) {
			const errorData = await response.json();
			throw error(response.status, errorData.detail || 'Failed to get meeting');
		}
		
		const meeting = await response.json();
		return json(meeting);
	} catch (err) {
		console.error('Error fetching meeting:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};

// POST handler for stopping a meeting
export const POST: RequestHandler = async ({ params, request, fetch, url }) => {
	try {
		const { meetingId } = params;
		
		// Check if we're handling the stop endpoint
		if (url.pathname.endsWith('/stop')) {
			const response = await fetch(`${BACKEND_API_URL}/meetings/${meetingId}/stop`, {
				method: 'POST'
			});
			
			if (!response.ok) {
				const errorData = await response.json();
				throw error(response.status, errorData.detail || 'Failed to stop meeting');
			}
			
			const result = await response.json();
			return json(result);
		}
		
		// For other POST requests to a specific meeting ID (if needed)
		const meetingData = await request.json();
		const response = await fetch(`${BACKEND_API_URL}/meetings/${meetingId}`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(meetingData)
		});
		
		if (!response.ok) {
			const errorData = await response.json();
			throw error(response.status, errorData.detail || 'Failed to update meeting');
		}
		
		const meeting = await response.json();
		return json(meeting);
	} catch (err) {
		console.error('Error processing meeting action:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};