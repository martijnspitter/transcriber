import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Get backend API URL from environment variable
const BACKEND_API_URL = import.meta.env.BACKEND_API_URL || 'http://localhost:8000';

// GET handler for retrieving a specific meeting
export const GET: RequestHandler = async ({ params, fetch }) => {
	try {
		const { meetingId } = params;
		const response = await fetch(`${BACKEND_API_URL}/meeting-status?id=${meetingId}`);

		if (!response.ok) {
			const errorData = await response.json();
			throw error(response.status, errorData.detail || 'Failed to get meeting');
		}

		const meeting = await response.json();
		return json(meeting);
	} catch (err) {
		console.error('Error fetching meeting status:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};
