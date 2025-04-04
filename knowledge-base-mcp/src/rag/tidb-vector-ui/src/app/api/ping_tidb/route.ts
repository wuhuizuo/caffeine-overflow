import { NextRequest, NextResponse } from 'next/server';

// Assuming Flask backend runs on port 5000
const FLASK_BACKEND_URL = process.env.FLASK_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: NextRequest) {
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

    const flaskResponse = await fetch(`${FLASK_BACKEND_URL}/api/ping_tidb`, {
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
        errorMessage = `Could not connect to the backend service at ${FLASK_BACKEND_URL}. Please ensure it's running.`;
        return NextResponse.json({ success: false, message: errorMessage }, { status: 503 }); // Service Unavailable
    }
    
    return NextResponse.json({ success: false, message: 'An unexpected error occurred: ' + errorMessage }, { status: 500 });
  }
} 