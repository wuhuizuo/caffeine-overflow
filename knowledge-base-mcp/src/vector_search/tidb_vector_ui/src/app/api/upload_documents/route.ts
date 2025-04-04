import { NextRequest, NextResponse } from 'next/server';

const backendApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

export async function POST(request: NextRequest) {
  // Ensure the backend URL is configured
  if (!backendApiUrl) {
    console.error('Error: NEXT_PUBLIC_API_BASE_URL environment variable is not set.');
    return NextResponse.json({ success: false, message: 'Backend service URL is not configured.' }, { status: 500 });
  }

  try {
    // Next.js automatically handles multipart/form-data
    const formData = await request.formData();
    
    // Expect connection_string in the FormData
    const connection_string = formData.get('connection_string');
    
    // Log received form data (excluding files for brevity)
    console.log('Received formData keys:', Array.from(formData.keys()));
    console.log('connection_string present:', !!connection_string);
    console.log('table_name:', formData.get('table_name'));
    console.log('api_key_type:', formData.get('api_key_type'));
    console.log('api_key:', formData.get('api_key') ? '******' : 'Not provided');

    // Basic validation on Next.js side (optional, Flask also validates)
    if (!connection_string) {
        return NextResponse.json({ success: false, message: 'Connection string is required.' }, { status: 400 });
    }
    if (!formData.get('table_name') || !formData.get('api_key_type') || !formData.get('api_key')) {
       return NextResponse.json({ success: false, message: 'Missing required fields (table name, api type, api key)' }, { status: 400 });
    }
    
    // Check if files are present (essential now)
    const files = formData.getAll('files[]');
    if (!files || files.length === 0 || (files.length === 1 && (files[0] as File).size === 0)) {
         return NextResponse.json({ success: false, message: 'No files found in the request for processing.' }, { status: 400 });
    }

    // Forward the request (including files) to the Flask backend
    const flaskResponse = await fetch(`${backendApiUrl}/api/upload_documents`, {
      method: 'POST',
      headers: {
        // Content-Type is set automatically by fetch when using FormData
        // Forward cookies if needed for session
        'Cookie': request.headers.get('cookie') || '',
      },
      body: formData, // Pass the FormData directly
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

    return NextResponse.json(data);

  } catch (error) {
    console.error('Error in /api/upload_documents:', error);
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