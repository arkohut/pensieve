import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/config')({
  component: ConfigPage,
});

function ConfigPage() {
  return <div className="p-4">Config page placeholder (Task 24)</div>;
}
