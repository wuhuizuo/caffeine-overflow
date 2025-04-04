import { NextRequest, NextResponse } from 'next/server';

const FLASK_BACKEND_URL = process.env.FLASK_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { table_name, query, k, threshold, api_key_type, api_key, connection_string } = body;

    // Basic validation
    if (!table_name || !query || !api_key_type || !api_key || k === undefined || threshold === undefined || !connection_string) {
      return NextResponse.json({ success: false, message: 'Missing required fields for retrieval test (including connection string)' }, { status: 400 });
    }

    // Forward the request to the Flask backend using form data
    const formData = new URLSearchParams();
    formData.append('table_name', table_name);
    formData.append('query', query);
    formData.append('k', k.toString());
    formData.append('threshold', threshold.toString());
    formData.append('api_key_type', api_key_type);
    formData.append('api_key', api_key);
    formData.append('connection_string', connection_string);

    const flaskResponse = await fetch(`${FLASK_BACKEND_URL}/api/test_retrieval`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        // Forward cookies if needed for session
        'Cookie': request.headers.get('cookie') || '',
      },
      body: formData.toString(),
    });

    const data = await flaskResponse.json();

    if (!flaskResponse.ok) {
       // Handle specific errors like connection failure
       if (flaskResponse.status === 400 && data.message?.includes('Connection string not found')) {
         return NextResponse.json(
           { success: false, message: 'Connection test failed or not performed. Please test connection again.' }, 
           { status: 400 }
         );
       }
      return NextResponse.json(data, { status: flaskResponse.status });
    }

    // The Flask endpoint returns { success: true, results: [...] } or { success: false, message: ... }
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error in /api/test_retrieval:', error);
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