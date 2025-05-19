<script lang="ts">
  import { generateLogo } from '$lib/logoGenerator';

  interface Props {
    size?: number;
    class_?: string;
    withBorder?: boolean;
    hasGap?: boolean;
  }

  let {
    size = 32,
    class_ = '',
    withBorder = true,
    hasGap = true
  }: Props = $props();

  let logoSvg = $derived(generateLogo(size, withBorder, hasGap));
</script>

<div class={`${class_}`}>
  {@html logoSvg}
</div>
