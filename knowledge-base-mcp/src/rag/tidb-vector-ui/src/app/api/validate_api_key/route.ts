import { NextRequest, NextResponse } from 'next/server';

const FLASK_BACKEND_URL = process.env.FLASK_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { api_key_type, api_key } = body;

    if (!api_key_type || !api_key) {
      return NextResponse.json({ success: false, message: 'API Key Type and API Key are required.' }, { status: 400 });
    }

    // Forward the request to the Flask backend using form data
    const formData = new URLSearchParams();
    formData.append('api_key_type', api_key_type);
    formData.append('api_key', api_key);

    console.log(`Proxying API Key validation request for type: ${api_key_type}`);

    const flaskResponse = await fetch(`${FLASK_BACKEND_URL}/api/validate_api_key`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': request.headers.get('cookie') || '',
      },
      body: formData.toString(),
    });

    // Read response body regardless of status code
    const data = await flaskResponse.json();

    // Return the exact response (status + body) from Flask
    return NextResponse.json(data, { status: flaskResponse.status });

  } catch (error) {
    console.error('Error in /api/validate_api_key:', error);
    let errorMessage = 'Internal Server Error';
    if (error instanceof Error) {
        errorMessage = error.message;
    }
    if (error instanceof TypeError && error.message.includes('fetch failed')) {
        errorMessage = `Could not connect to the backend service at ${FLASK_BACKEND_URL}. Please ensure it's running.`;
        return NextResponse.json({ success: false, message: errorMessage }, { status: 503 });
    }
    return NextResponse.json({ success: false, message: 'An unexpected error occurred: ' + errorMessage }, { status: 500 });
  }
} 