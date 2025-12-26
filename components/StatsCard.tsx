import Link from 'next/link';
import type { StatsCardProps } from '@/types';

export default function StatsCard({ title, value, change, isPositive, icon, href }: StatsCardProps) {
  const content = (
    <>
      <div className="stats-card-header">
        <div className="stats-card-icon">{icon}</div>
        {change && (
          <span className={`stats-card-change ${isPositive ? 'positive' : 'negative'}`}>
            {change}
          </span>
        )}
      </div>
      <h3 className="stats-card-title">{title}</h3>
      <p className="stats-card-value">{value}</p>
    </>
  );

  if (href) {
    return (
      <Link href={href} className="stats-card stats-card-link">
        {content}
      </Link>
    );
  }

  return <div className="stats-card">{content}</div>;
}

