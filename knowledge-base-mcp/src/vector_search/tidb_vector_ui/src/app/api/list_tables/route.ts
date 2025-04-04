import { NextRequest, NextResponse } from 'next/server';

const FLASK_BACKEND_URL = process.env.FLASK_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: NextRequest) {
  try {
    // Get connection string from JSON body
    const body = await request.json();
    const { connection_string } = body;

    if (!connection_string) {
         return NextResponse.json(
           { success: false, message: 'Connection string is required in the request body.' }, 
           { status: 400 }
         );
    }

    // Pass connection string directly to Flask endpoint via form data
    // ** Flask's /api/list_tables MUST be updated to handle POST and read this value **
    const formData = new URLSearchParams();
    formData.append('connection_string', connection_string);
    
    console.log(`Proxying list_tables POST request for (masked): ${connection_string.substring(0, 20)}...`);
    
    const flaskResponse = await fetch(`${FLASK_BACKEND_URL}/api/list_tables`, {
      // Using POST now
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': request.headers.get('cookie') || '', // Keep cookie for Flask session just in case it's still needed for other things
      },
      body: formData.toString(), // Send connection string in body
      cache: 'no-store', 
    });

    const data = await flaskResponse.json();

    if (!flaskResponse.ok) {
      // Check if Flask returned the specific session error
      if (flaskResponse.status === 400 && data.message?.includes('Connection string not found')) {
         return NextResponse.json(
           { success: false, message: 'Connection invalid or Flask backend session error. Please test connection again. (Flask backend may need update)' }, 
           { status: 400 }
         );
      } else if (flaskResponse.status === 405) { // Method Not Allowed
           return NextResponse.json(
             { success: false, message: 'Flask backend /api/list_tables does not support POST. (Flask backend needs update)' }, 
             { status: 405 }
           );
      }
      return NextResponse.json(data, { status: flaskResponse.status });
    }

    return NextResponse.json(data);

  } catch (error) {
    console.error('Error in /api/list_tables:', error);
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