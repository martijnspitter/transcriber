import type { Handle } from '@sveltejs/kit';

// This hook handles all server-side requests
export const handle: Handle = async ({ event, resolve }) => {
	// Special handling for API routes that we're proxying to our backend
	if (event.url.pathname.startsWith('/api/')) {
		// Log API requests for debugging
		console.log(`[API Request] ${event.request.method} ${event.url.pathname}`);
	}

	// Continue processing the request
	const response = await resolve(event);
	return response;
};