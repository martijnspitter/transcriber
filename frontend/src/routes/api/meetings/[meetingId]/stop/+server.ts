import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Get backend API URL from environment variable
const BACKEND_API_URL = import.meta.env.BACKEND_API_URL || 'http://localhost:8000/api';

// POST handler for stopping a meeting
export const POST: RequestHandler = async ({ params, fetch }) => {
	try {
		const { meetingId } = params;
		
		const response = await fetch(`${BACKEND_API_URL}/meetings/${meetingId}/stop`, {
			method: 'POST'
		});
		
		if (!response.ok) {
			const errorData = await response.json();
			throw error(response.status, errorData.detail || 'Failed to stop meeting');
		}
		
		const result = await response.json();
		return json(result);
	} catch (err) {
		console.error('Error stopping meeting:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};