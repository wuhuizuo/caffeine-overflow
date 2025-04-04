import { NextRequest, NextResponse } from 'next/server';

const FLASK_BACKEND_URL = process.env.FLASK_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { table_name, connection_string } = body;

    if (!table_name || !connection_string) {
      return NextResponse.json({ success: false, message: 'Table name and connection string are required' }, { status: 400 });
    }

    // Forward the request to the Flask backend
    const formData = new URLSearchParams();
    formData.append('table_name', table_name);
    formData.append('connection_string', connection_string);

    const flaskResponse = await fetch(`${FLASK_BACKEND_URL}/api/drop_table`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        // Forward cookies if Flask session depends on them
        'Cookie': request.headers.get('cookie') || '',
      },
      body: formData.toString(),
    });

    const data = await flaskResponse.json();

    if (!flaskResponse.ok) {
       // Special handling for connection error
       if (flaskResponse.status === 400 && data.message?.includes('Connection string not found')) {
         return NextResponse.json(
           { success: false, message: 'Connection test failed or not performed. Please test connection again.' }, 
           { status: 400 }
         );
       }
      return NextResponse.json(data, { status: flaskResponse.status });
    }

    return NextResponse.json(data);

  } catch (error) {
    console.error('Error in /api/drop_table:', error);
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