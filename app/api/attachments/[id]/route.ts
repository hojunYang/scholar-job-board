import { readFile } from 'fs/promises';
import path from 'path';
import { NextRequest } from 'next/server';
import { getNoticeAttachmentById } from '@/lib/queries';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface RouteContext {
  params: Promise<{ id: string }>;
}

function buildContentDisposition(dispositionType: 'attachment' | 'inline', filename: string) {
  const encodedFilename = encodeURIComponent(filename);
  return `${dispositionType}; filename*=UTF-8''${encodedFilename}`;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const attachmentId = Number(id);

  if (!Number.isInteger(attachmentId) || attachmentId <= 0) {
    return new Response('Invalid attachment id', { status: 400 });
  }

  const attachment = getNoticeAttachmentById(attachmentId);
  if (!attachment) {
    return new Response('Attachment not found', { status: 404 });
  }

  const dispositionType = request.nextUrl.searchParams.get('download') === '1' ? 'attachment' : 'inline';
  const absolutePath = path.join(process.cwd(), attachment.storagePath);

  try {
    const fileBuffer = await readFile(absolutePath);

    return new Response(fileBuffer, {
      headers: {
        'Content-Type': attachment.mimeType || 'application/octet-stream',
        'Content-Length': fileBuffer.byteLength.toString(),
        'Content-Disposition': buildContentDisposition(dispositionType, attachment.originalFilename),
      },
    });
  } catch {
    return new Response('Attachment file not found', { status: 404 });
  }
}
