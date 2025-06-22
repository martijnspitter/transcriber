import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const BACKEND_API_URL = import.meta.env.BACKEND_API_URL || 'http://localhost:8000';

// POST handler for stopping a meeting
export const POST: RequestHandler = async ({ params, fetch, }) => {
	try {
		const { meetingId } = params;

		// Check if we're handling the stop endpoint
			const response = await fetch(`${BACKEND_API_URL}/stop-recording`, {
				method: 'POST',
				headers: {
        'Content-Type': 'application/json',
        },
        body: JSON.stringify({ meeting_id: meetingId }),
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw error(response.status, errorData.detail || 'Failed to stop meeting');
			}

			const result = await response.json();
			return json(result);
	} catch (err) {
		console.error('Error fetching meeting status:', err);
		if (err instanceof Error) {
			throw error(500, err.message);
		}
		throw error(500, 'Unknown error occurred');
	}
};
