import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Config } from '$/components/config/Config';

export const Route = createFileRoute('/config')({
  component: ConfigPage,
});

function ConfigPage() {
  const navigate = useNavigate();
  return <Config onBack={() => void navigate({ to: '/' })} />;
}
