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
  Image,
  type LucideProps,
} from 'lucide-react';

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
  Image,
} as const;

type IconName = keyof typeof iconMap;

interface Props extends LucideProps {
  name: IconName | string;
}

export function LucideIcon({ name, ...props }: Props) {
  const Icon = iconMap[name as IconName] ?? Hexagon;
  return <Icon {...props} />;
}
