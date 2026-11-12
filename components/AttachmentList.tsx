import type { NoticeAttachment } from '@/types';
import Icon from './Icon';
export default function AttachmentList({ attachments = [] }: { attachments?: NoticeAttachment[] }) {
  if (!attachments.length) return <p className="helper-text">등록된 첨부파일이 없습니다.</p>;
  return <div className="attachment-list">{attachments.map(attachment => <a key={attachment.id} href={attachment.downloadPath} target="_blank" rel="noreferrer"><span className="attachment-icon"><Icon name="file" size={20}/></span><span><strong>{attachment.originalFilename}</strong>{attachment.fileSize ? <small>{(attachment.fileSize / 1024).toFixed(0)} KB</small> : null}</span><Icon name="external" size={17}/></a>)}</div>;
}
