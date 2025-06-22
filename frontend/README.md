# Meeting Transcriber Frontend

The user interface for the Meeting Transcriber application, built with SvelteKit and TailwindCSS.

## Overview

This frontend allows users to:
- Record meetings from any application
- Manage participants
- See real-time recording status updates
- View markdown-formatted meeting summaries
- Track the status of recording and processing

## Developing

Once you've installed dependencies with `npm install`, start the development server:

```bash
npm run dev

# or start the server and open the app in a new browser tab
npm run dev -- --open
```

The application expects the backend API to be running at http://localhost:8000. Make sure the backend server is running before using the frontend.

## Building

To create a production version of the frontend:

```bash
npm run build
```

You can preview the production build with `npm run preview`.

## Features

### Real-time Status Updates
- Live status display for recording and processing stages
- Duration tracking for recordings
- Visual indicators for different processing states

### Participant Management
- Add participants with custom names
- Remove participants as needed
- Track meeting attendees

### Markdown Rendering
- Display of AI-generated meeting summaries in formatted markdown
- Support for headings, lists, code blocks, and emphasis
- Custom styling for better readability

## Technology Stack

- **SvelteKit** - Modern framework for building web applications
- **TypeScript** - Type-safe JavaScript
- **TailwindCSS** - Utility-first CSS framework
- **Tailwind Typography** - For styling markdown content

## Project Structure

- `src/components/` - Reusable UI components
- `src/routes/` - SvelteKit pages and layouts
- `src/services/` - API integration and data services
- `src/lib/` - Utility functions and shared code
