import { NextRequest, NextResponse } from 'next/server';

const backendApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

export async function POST(request: NextRequest) {
  if (!backendApiUrl) {
    console.error('Error: NEXT_PUBLIC_API_BASE_URL environment variable is not set.');
    return NextResponse.json({ success: false, message: 'Backend service URL is not configured.' }, { status: 500 });
  }

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

    const flaskResponse = await fetch(`${backendApiUrl}/api/validate_api_key`, {
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
        errorMessage = `Could not connect to the backend service at ${backendApiUrl}. Please ensure it's running.`;
        return NextResponse.json({ success: false, message: errorMessage }, { status: 503 });
    }
    return NextResponse.json({ success: false, message: 'An unexpected error occurred: ' + errorMessage }, { status: 500 });
  }
} 