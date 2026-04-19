import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const url = new URL(request.url);
  url.pathname = url.pathname.replace(/^\/api\/auth/, '/auth');
  return NextResponse.redirect(url);
}

export async function POST(request: Request) {
  const url = new URL(request.url);
  url.pathname = url.pathname.replace(/^\/api\/auth/, '/auth');
  return NextResponse.redirect(url);
}
