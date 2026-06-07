import { SCENES } from './scenes';

export function Deck() {
  const requested = new URLSearchParams(window.location.search).get('scene');
  const scene = SCENES.find((s) => s.id === requested) ?? SCENES[0];
  const Active = scene.Component;

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-6">
      <Active />
    </div>
  );
}
