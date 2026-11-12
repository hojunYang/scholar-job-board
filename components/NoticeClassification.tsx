interface Props {
  main_category: string | null;
  subcategory: string | null;
  classification_status: string;
}

export default function NoticeClassification(notice: Props) {
  return (
    <>
      <span className="badge badge-category">{notice.main_category || '분류 대기'}</span>
      {notice.subcategory && <span className="text-xs text-gray-600">{notice.subcategory}</span>}
      {notice.classification_status === 'needs_review' && <span className="text-xs text-amber-700">내용 확인 필요</span>}
    </>
  );
}
