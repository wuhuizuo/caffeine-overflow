import { NextRequest, NextResponse } from 'next/server';

// Get the backend URL from the environment variable set by Docker Compose
const backendApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL; // Renamed variable

export async function POST(request: NextRequest) {
  // Ensure the backend URL is configured
  if (!backendApiUrl) {
    console.error('Error: NEXT_PUBLIC_API_BASE_URL environment variable is not set.');
    return NextResponse.json({ success: false, message: 'Backend service URL is not configured.' }, { status: 500 });
  }

  try {
    const body = await request.json();
    const { connection_string } = body;

    if (!connection_string) {
      return NextResponse.json({ success: false, message: 'Connection string is required' }, { status: 400 });
    }

    // Forward the request to the Flask backend
    // Flask expects form data, so we create FormData
    const formData = new URLSearchParams();
    formData.append('connection_string', connection_string);

    const flaskResponse = await fetch(`${backendApiUrl}/api/ping_tidb`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    const data = await flaskResponse.json();

    if (!flaskResponse.ok) {
      // Forward the error status and message from Flask if possible
      return NextResponse.json(data, { status: flaskResponse.status });
    }

    // Return the successful response from Flask
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error in /api/ping_tidb:', error);
    let errorMessage = 'Internal Server Error';
    if (error instanceof Error) {
        errorMessage = error.message;
    }
    // Handle fetch errors (e.g., Flask server not running)
    if (error instanceof TypeError && error.message.includes('fetch failed')) {
        errorMessage = `Could not connect to the backend service at ${backendApiUrl}. Please ensure it's running.`;
        return NextResponse.json({ success: false, message: errorMessage }, { status: 503 }); // Service Unavailable
    }
    
    return NextResponse.json({ success: false, message: 'An unexpected error occurred: ' + errorMessage }, { status: 500 });
  }
} 