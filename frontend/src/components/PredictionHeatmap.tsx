import type { CSSProperties } from 'react';
import { WEEKDAYS, type PredictionBucket } from '../services/predictions';

const DAY_LABELS: Record<(typeof WEEKDAYS)[number], string> = {
  MONDAY: 'Mon',
  TUESDAY: 'Tue',
  WEDNESDAY: 'Wed',
  THURSDAY: 'Thu',
  FRIDAY: 'Fri',
  SATURDAY: 'Sat',
  SUNDAY: 'Sun',
};

export function PredictionHeatmap({ buckets }: { buckets: PredictionBucket[] }) {
  const lookup = new Map(buckets.map((bucket) => [
    `${bucket.day_of_week}:${bucket.hour_of_day}`,
    bucket,
  ]));

  return <div className="heatmap-scroll" aria-label="Weekly occupancy prediction heatmap">
    <div className="heatmap" data-testid="prediction-heatmap">
      <span className="heatmap-corner" aria-hidden="true" />
      {Array.from({ length: 24 }, (_, hour) => <span className="heatmap-hour" key={hour}>{hour}</span>)}
      {WEEKDAYS.map((day) => <div className="heatmap-row" key={day}>
        <span className="heatmap-day">{DAY_LABELS[day]}</span>
        {Array.from({ length: 24 }, (_, hour) => {
          const bucket = lookup.get(`${day}:${hour}`);
          const occupancy = bucket?.expected_occupancy_rate;
          const availability = bucket?.expected_availability_rate;
          const label = bucket
            ? `${day} ${hour}:00 — occupancy ${(occupancy! * 100).toFixed(1)}%, availability ${(availability! * 100).toFixed(1)}%`
            : `${day} ${hour}:00 — missing bucket`;
          return <span
            className={`heatmap-cell${bucket ? '' : ' heatmap-missing'}`}
            data-testid="prediction-bucket"
            key={hour}
            aria-label={label}
            title={label}
            style={{ '--occupancy': occupancy ?? 0 } as CSSProperties}
          >{bucket ? Math.round(occupancy! * 100) : '—'}</span>;
        })}
      </div>)}
    </div>
  </div>;
}
