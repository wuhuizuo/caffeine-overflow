import { NextRequest, NextResponse } from 'next/server';

const backendApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

export async function POST(request: NextRequest) {
  if (!backendApiUrl) {
    console.error('Error: NEXT_PUBLIC_API_BASE_URL environment variable is not set.');
    return NextResponse.json({ success: false, message: 'Backend service URL is not configured.' }, { status: 500 });
  }

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

    const flaskResponse = await fetch(`${backendApiUrl}/api/drop_table`, {
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
        errorMessage = `Could not connect to the backend service at ${backendApiUrl}. Please ensure it's running.`;
        return NextResponse.json({ success: false, message: errorMessage }, { status: 503 });
    }
    return NextResponse.json({ success: false, message: 'An unexpected error occurred: ' + errorMessage }, { status: 500 });
  }
} 