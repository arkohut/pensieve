<script lang="ts">
  import { 
    Chrome,
    Globe,
    Code,
    LayoutGrid,
    MessageSquareCode,
    Eye,
    SquareTerminal,
    Phone,
    Folder,
    Mail,
    NotebookTabs,
    CalendarFold,
    Bell,
    Atom,
    Compass,
    Settings,
    CircleDollarSign,
    Activity,
    Search,
    Lock,
    CloudDownload,
    Bot,
    Github,
    Youtube,
    Hexagon,
    Image
  } from '@lucide/svelte';

  const iconMap = {
    Chrome,
    Globe,
    Code,
    LayoutGrid,
    MessageSquareCode,
    Eye,
    SquareTerminal,
    Phone,
    Folder,
    Mail,
    NotebookTabs,
    CalendarFold,
    Bell,
    Atom,
    Compass,
    Settings,
    CircleDollarSign,
    Activity,
    Search,
    Lock,
    CloudDownload,
    Bot,
    Github,
    Youtube,
    Hexagon,
    Image
  };

  let { name, ...extraProps } = $props();

  let Icon = iconMap[name] || Hexagon;
</script>

<Icon {name} {...extraProps} />