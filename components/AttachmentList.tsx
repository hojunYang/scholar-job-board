import type { NoticeAttachment } from '@/types';

interface AttachmentListProps {
  attachments?: NoticeAttachment[];
}

function formatFileSize(fileSize: number | null) {
  if (!fileSize || fileSize <= 0) {
    return null;
  }

  if (fileSize >= 1024 * 1024) {
    return `${(fileSize / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${(fileSize / 1024).toFixed(1)} KB`;
}

export default function AttachmentList({ attachments = [] }: AttachmentListProps) {
  if (attachments.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
        첨부파일이 없습니다.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {attachments.map((attachment) => {
        const fileSize = formatFileSize(attachment.fileSize);

        return (
          <div
            key={attachment.id}
            className="flex flex-col gap-3 rounded-lg border border-gray-200 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">{attachment.originalFilename}</p>
              {fileSize && <p className="mt-1 text-xs text-gray-500">{fileSize}</p>}
            </div>

            <a
              href={attachment.downloadPath}
              className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
            >
              다운로드
            </a>
          </div>
        );
      })}
    </div>
  );
}
