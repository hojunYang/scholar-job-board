import type { EligibilityConditions as Conditions } from '@/types';

export default function EligibilityConditions({ value }: { value: string | null }) {
  let conditions: Conditions | null = null;
  try { conditions = value ? JSON.parse(value) : null; } catch { /* Legacy data can be missing. */ }
  const evidence = conditions && Array.isArray(conditions.evidence) ? conditions.evidence : [];
  return (
    <section className="mb-8">
      <h2 className="text-xl font-bold text-gray-900 mb-3">지원 대상·상세 조건</h2>
      {evidence.length ? (
        <ul className="list-disc pl-5 space-y-2 text-gray-700 whitespace-pre-wrap">
          {evidence.map((clause, index) => <li key={index}>{clause}</li>)}
        </ul>
      ) : <p className="text-gray-500">DB에 명시된 지원 조건이 없습니다. 원문과 첨부파일을 확인해 주세요.</p>}
    </section>
  );
}
