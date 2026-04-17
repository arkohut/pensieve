import { type ReactNode } from 'react';
import { EntityImage } from './EntityImage';
import { EntityDetail } from './EntityDetail';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity;
  showDetails: boolean;
  toggleDetails: () => void;
  leftIcon?: ReactNode;
}

export function EntityView({ entity, showDetails, toggleDetails, leftIcon }: Props) {
  return (
    <div className="relative flex h-full flex-col md:flex-row">
      <EntityImage
        entity={entity}
        showDetails={showDetails}
        toggleDetails={toggleDetails}
        leftIcon={leftIcon}
      />
      {showDetails && <EntityDetail entity={entity} />}
    </div>
  );
}
