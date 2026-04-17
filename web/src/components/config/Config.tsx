import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Save, RotateCw, ArrowLeft, Loader } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Input } from '$/components/ui/input';
import { Label } from '$/components/ui/label';
import { Checkbox } from '$/components/ui/checkbox';
import { Textarea } from '$/components/ui/textarea';
import { Alert, AlertDescription } from '$/components/ui/alert';
import { HealthCheck } from '$/components/common/HealthCheck';
import { PageHeader } from '$/components/common/PageHeader';
import { ConfigSection } from './ConfigSection';
import { apiEndpoint } from '$/lib/api/client';

interface Props {
  onBack: () => void;
}

type SectionKey = 'general' | 'serve' | 'record' | 'watch' | 'ocr' | 'vlm' | 'embedding';

function deepSet(obj: Record<string, unknown>, path: string[], value: unknown): Record<string, unknown> {
  const result = { ...obj };
  let current: Record<string, unknown> = result;
  for (let i = 0; i < path.length - 1; i++) {
    const key = path[i];
    current[key] = { ...(current[key] as Record<string, unknown> ?? {}) };
    current = current[key] as Record<string, unknown>;
  }
  current[path[path.length - 1]] = value;
  return result;
}

function deepGet(obj: unknown, path: string[]): unknown {
  let current = obj;
  for (const key of path) {
    if (current == null || typeof current !== 'object') return null;
    current = (current as Record<string, unknown>)[key];
  }
  return current ?? null;
}

export function Config({ onBack }: Props) {
  const { t } = useTranslation();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changes, setChanges] = useState<Record<string, unknown>>({});
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  const [servicesRestarting, setServicesRestarting] = useState(false);

  const [uiState, setUiState] = useState({
    inputsDisabled: { ocr: false, embedding: false },
    pluginDisabled: { ocr: false, vlm: false },
  });

  const [sectionOpen, setSectionOpen] = useState<Record<SectionKey, boolean>>(() => {
    try {
      const saved = localStorage.getItem('configSectionStates');
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    return { general: false, serve: false, record: false, watch: false, ocr: false, vlm: false, embedding: false };
  });

  const vlmPromptRef = useRef<HTMLTextAreaElement | null>(null);
  const appBlacklistRef = useRef<HTMLTextAreaElement | null>(null);

  function toggleSection(key: SectionKey) {
    setSectionOpen((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem('configSectionStates', JSON.stringify(next));
      return next;
    });
  }

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiEndpoint}/config`);
      if (!res.ok) throw new Error(`Error fetching config: ${res.status} ${res.statusText}`);
      const data = await res.json();
      setConfig(data);
      setChanges({});
      setUiState({
        inputsDisabled: {
          ocr: data?.ocr?.use_local ?? false,
          embedding: data?.embedding?.use_local ?? false,
        },
        pluginDisabled: {
          ocr: !(data?.ocr?.enabled ?? true),
          vlm: !(data?.vlm?.enabled ?? true),
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchConfig(); }, [fetchConfig]);

  useEffect(() => {
    document.title = `Pensieve - ${t('config.title')}`;
  }, [t]);

  function handleChange(path: string[], value: unknown) {
    setChanges((prev) => deepSet(prev, path, value));
  }

  function getVal(path: string[]): unknown {
    const changed = deepGet(changes, path);
    if (changed !== null && changed !== undefined) return changed;
    return deepGet(config, path);
  }

  function handleUseLocalChange(feature: 'ocr' | 'embedding', newValue: boolean) {
    handleChange([feature, 'use_local'], newValue);
    setUiState((prev) => ({
      ...prev,
      inputsDisabled: { ...prev.inputsDisabled, [feature]: newValue },
    }));
  }

  function handlePluginEnabledChange(plugin: 'ocr' | 'vlm', newValue: boolean) {
    handleChange([plugin, 'enabled'], newValue);
    setUiState((prev) => ({
      ...prev,
      pluginDisabled: { ...prev.pluginDisabled, [plugin]: !newValue },
    }));
  }

  async function saveConfig() {
    if (Object.keys(changes).length === 0) {
      toast.message(t('config.title'), { description: t('config.noChanges') });
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${apiEndpoint}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(changes),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail || `Error: ${res.status}`);
      }
      const result = await res.json();
      toast.success(t('config.title'), { description: t('config.savedSuccessfully') });
      if (result.restart_required && Object.values(result.restart_required).some(Boolean)) {
        if (result.restart_required.serve) setServicesRestarting(true);
      }
      await fetchConfig();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(msg);
      toast.error(t('config.error'), { description: msg });
    } finally {
      setSaving(false);
    }
  }

  async function confirmRestart() {
    setShowRestartConfirm(false);
    setSaving(true);
    setServicesRestarting(true);
    try {
      const res = await fetch(`${apiEndpoint}/config/restart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serve: true, watch: true, record: true }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail || `Error: ${res.status}`);
      }
      toast.success(t('config.title'), { description: t('config.servicesRestarting') });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(msg);
      toast.error(t('config.error'), { description: msg });
      setServicesRestarting(false);
    } finally {
      setSaving(false);
    }
  }

  function adjustTextareaHeight(el: HTMLTextAreaElement | null) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 72)}px`;
  }

  function getAppBlacklistString(): string {
    const bl = getVal(['app_blacklist']);
    return Array.isArray(bl) ? bl.join('\n') : String(bl ?? '');
  }

  const hasChanges = Object.keys(changes).length > 0;

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader size={36} className="animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      {servicesRestarting && (
        <HealthCheck onStatusChange={() => setServicesRestarting(false)} />
      )}

      <PageHeader
        sticky
        maxWidth="max-w-5xl"
        left={
          <>
            <Button variant="ghost" size="sm" onClick={onBack}>
              <ArrowLeft size={16} className="mr-2" />
              {t('back')}
            </Button>
            <h1 className="text-xl font-bold">{t('config.title')}</h1>
          </>
        }
        right={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRestartConfirm(true)}
              disabled={saving || servicesRestarting}
            >
              <RotateCw size={16} className="mr-2" />
              {t('config.restartServices')}
            </Button>
            <Button
              size="sm"
              onClick={() => void saveConfig()}
              disabled={saving || servicesRestarting || !hasChanges}
            >
              <Save size={16} className="mr-2" />
              {t('config.saveButton')}
            </Button>
          </>
        }
      />

      <div className="container mx-auto max-w-5xl p-4">
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {showRestartConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-lg bg-background p-6 shadow-xl">
            <h3 className="mb-2 text-lg font-medium">{t('config.restartConfirmTitle')}</h3>
            <p className="mb-4 text-muted-foreground">{t('config.restartConfirmMessage')}</p>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setShowRestartConfirm(false)}>
                {t('config.cancel')}
              </Button>
              <Button variant="destructive" onClick={() => void confirmRestart()}>
                {t('config.confirm')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {config && (
        <>
          {/* OCR */}
          <ConfigSection
            title={t('config.ocr.title')}
            description={t('config.ocr.description')}
            open={sectionOpen.ocr}
            onOpenChange={() => toggleSection('ocr')}
          >
            <div className="flex items-start space-x-2">
              <Checkbox id="enable-ocr" checked={!!getVal(['ocr', 'enabled'])} onCheckedChange={() => handlePluginEnabledChange('ocr', !getVal(['ocr', 'enabled']))} />
              <div className="space-y-1 leading-none">
                <Label htmlFor="enable-ocr">{t('config.ocr.enabled', { defaultValue: 'Enable OCR Plugin' })}</Label>
                <p className="text-sm text-muted-foreground">{t('config.ocr.enabledDesc', { defaultValue: 'Whether to enable the OCR plugin.' })}</p>
              </div>
            </div>
            <div className="flex items-start space-x-2">
              <Checkbox id="use-local-ocr" checked={!!getVal(['ocr', 'use_local'])} disabled={uiState.pluginDisabled.ocr} onCheckedChange={() => { if (!uiState.pluginDisabled.ocr) handleUseLocalChange('ocr', !getVal(['ocr', 'use_local'])); }} />
              <Label htmlFor="use-local-ocr" className={uiState.pluginDisabled.ocr ? 'text-muted-foreground' : ''}>{t('config.ocr.useLocal')}</Label>
            </div>
            <div className="flex items-start space-x-2">
              <Checkbox id="force-jpeg-ocr" checked={!!getVal(['ocr', 'force_jpeg'])} disabled={uiState.pluginDisabled.ocr} onCheckedChange={() => { if (!uiState.pluginDisabled.ocr) handleChange(['ocr', 'force_jpeg'], !getVal(['ocr', 'force_jpeg'])); }} />
              <div className="space-y-1 leading-none">
                <Label htmlFor="force-jpeg-ocr" className={uiState.pluginDisabled.ocr ? 'text-muted-foreground' : ''}>{t('config.ocr.forceJpeg')}</Label>
                <p className="text-sm text-muted-foreground">{t('config.ocr.forceJpegDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="ocr-endpoint">{t('config.ocr.endpoint')}</Label>
                <Input id="ocr-endpoint" className="font-mono" value={String(getVal(['ocr', 'endpoint']) ?? '')} disabled={uiState.inputsDisabled.ocr || uiState.pluginDisabled.ocr} onChange={(e) => handleChange(['ocr', 'endpoint'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.ocr.endpointDesc')}</p>
              </div>
              <div>
                <Label htmlFor="ocr-token">{t('config.ocr.token')}</Label>
                <Input id="ocr-token" className="font-mono" type="password" value={getVal(['ocr', 'token']) === '********' ? '' : String(getVal(['ocr', 'token']) ?? '')} placeholder="********" disabled={uiState.inputsDisabled.ocr || uiState.pluginDisabled.ocr} onChange={(e) => { if (e.target.value) handleChange(['ocr', 'token'], e.target.value); }} />
              </div>
            </div>
            <div>
              <Label htmlFor="ocr-concurrency">{t('config.ocr.concurrency')}</Label>
              <Input id="ocr-concurrency" className="font-mono" type="number" value={String(getVal(['ocr', 'concurrency']) ?? '')} disabled={uiState.pluginDisabled.ocr} onChange={(e) => handleChange(['ocr', 'concurrency'], parseInt(e.target.value))} />
              <p className="mt-1 text-sm text-muted-foreground">{t('config.ocr.concurrencyDesc')}</p>
            </div>
          </ConfigSection>

          {/* VLM */}
          <ConfigSection
            title={t('config.vlm.title')}
            description={t('config.vlm.description')}
            open={sectionOpen.vlm}
            onOpenChange={() => toggleSection('vlm')}
          >
            <div className="mb-4 flex items-start space-x-2">
              <Checkbox id="enable-vlm" checked={!!getVal(['vlm', 'enabled'])} onCheckedChange={() => handlePluginEnabledChange('vlm', !getVal(['vlm', 'enabled']))} />
              <div className="space-y-1 leading-none">
                <Label htmlFor="enable-vlm">{t('config.vlm.enabled', { defaultValue: 'Enable VLM Plugin' })}</Label>
                <p className="text-sm text-muted-foreground">{t('config.vlm.enabledDesc', { defaultValue: 'Whether to enable the VLM plugin.' })}</p>
              </div>
            </div>
            <div>
              <Label htmlFor="model-name">{t('config.vlm.modelName')}</Label>
              <Input id="model-name" className="font-mono" value={String(getVal(['vlm', 'modelname']) ?? '')} disabled={uiState.pluginDisabled.vlm} onChange={(e) => handleChange(['vlm', 'modelname'], e.target.value)} />
              <p className="mt-1 text-sm text-muted-foreground">{t('config.vlm.modelNameDesc')}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="vlm-endpoint">{t('config.vlm.endpoint')}</Label>
                <Input id="vlm-endpoint" className="font-mono" value={String(getVal(['vlm', 'endpoint']) ?? '')} disabled={uiState.pluginDisabled.vlm} onChange={(e) => handleChange(['vlm', 'endpoint'], e.target.value)} />
              </div>
              <div>
                <Label htmlFor="vlm-token">{t('config.vlm.token')}</Label>
                <Input id="vlm-token" className="font-mono" type="password" value={getVal(['vlm', 'token']) === '********' ? '' : String(getVal(['vlm', 'token']) ?? '')} placeholder="********" disabled={uiState.pluginDisabled.vlm} onChange={(e) => { if (e.target.value) handleChange(['vlm', 'token'], e.target.value); }} />
              </div>
            </div>
            <div>
              <Label htmlFor="vlm-concurrency">{t('config.vlm.concurrency')}</Label>
              <Input id="vlm-concurrency" className="font-mono" type="number" value={String(getVal(['vlm', 'concurrency']) ?? '')} disabled={uiState.pluginDisabled.vlm} onChange={(e) => handleChange(['vlm', 'concurrency'], parseInt(e.target.value))} />
              <p className="mt-1 text-sm text-muted-foreground">{t('config.vlm.concurrencyDesc')}</p>
            </div>
            <div className="flex items-start space-x-2">
              <Checkbox id="force-jpeg-vlm" checked={!!getVal(['vlm', 'force_jpeg'])} disabled={uiState.pluginDisabled.vlm} onCheckedChange={() => { if (!uiState.pluginDisabled.vlm) handleChange(['vlm', 'force_jpeg'], !getVal(['vlm', 'force_jpeg'])); }} />
              <div className="space-y-1 leading-none">
                <Label htmlFor="force-jpeg-vlm" className={uiState.pluginDisabled.vlm ? 'text-muted-foreground' : ''}>{t('config.vlm.forceJpeg')}</Label>
                <p className="text-sm text-muted-foreground">{t('config.vlm.forceJpegDesc')}</p>
              </div>
            </div>
            <div>
              <Label htmlFor="vlm-prompt">{t('config.vlm.prompt')}</Label>
              <Textarea
                id="vlm-prompt"
                ref={vlmPromptRef}
                className="min-h-[72px] resize-none overflow-hidden font-mono"
                value={String(getVal(['vlm', 'prompt']) ?? '')}
                disabled={uiState.pluginDisabled.vlm}
                onInput={(e) => {
                  handleChange(['vlm', 'prompt'], (e.target as HTMLTextAreaElement).value);
                  adjustTextareaHeight(vlmPromptRef.current);
                }}
              />
              <p className="mt-1 text-sm text-muted-foreground">{t('config.vlm.promptDesc')}</p>
            </div>
          </ConfigSection>

          {/* Record */}
          <ConfigSection
            title={t('config.record.title')}
            description={t('config.record.description')}
            open={sectionOpen.record}
            onOpenChange={() => toggleSection('record')}
          >
            <div>
              <Label htmlFor="record-interval">{t('config.record.interval')}</Label>
              <Input id="record-interval" className="font-mono" type="number" value={String(getVal(['record_interval']) ?? '')} onChange={(e) => handleChange(['record_interval'], parseInt(e.target.value))} />
              <p className="mt-1 text-sm text-muted-foreground">{t('config.record.intervalDesc')}</p>
            </div>
            <div>
              <Label htmlFor="app-blacklist">{t('config.record.appBlacklist')}</Label>
              <Textarea
                id="app-blacklist"
                ref={appBlacklistRef}
                className="min-h-[72px] resize-none overflow-hidden font-mono"
                value={getAppBlacklistString()}
                placeholder={t('config.record.appBlacklistPlaceholder')}
                onInput={(e) => {
                  const lines = (e.target as HTMLTextAreaElement).value.split('\n').map((l) => l.trim()).filter(Boolean);
                  handleChange(['app_blacklist'], lines);
                  adjustTextareaHeight(appBlacklistRef.current);
                }}
              />
              <p className="mt-1 text-sm text-muted-foreground">{t('config.record.appBlacklistDesc')}</p>
            </div>
          </ConfigSection>

          {/* Watch */}
          <ConfigSection
            title={t('config.watch.title')}
            description={t('config.watch.description')}
            open={sectionOpen.watch}
            onOpenChange={() => toggleSection('watch')}
          >
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="rate-window-size">{t('config.watch.rateWindowSize')}</Label>
                <Input id="rate-window-size" className="font-mono" type="number" value={String(getVal(['watch', 'rate_window_size']) ?? '')} onChange={(e) => handleChange(['watch', 'rate_window_size'], parseInt(e.target.value))} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.watch.rateWindowSizeDesc')}</p>
              </div>
              <div>
                <Label htmlFor="sparsity-factor">{t('config.watch.sparsityFactor')}</Label>
                <Input id="sparsity-factor" className="font-mono" type="number" step="0.1" value={String(getVal(['watch', 'sparsity_factor']) ?? '')} onChange={(e) => handleChange(['watch', 'sparsity_factor'], parseFloat(e.target.value))} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.watch.sparsityFactorDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="processing-interval">{t('config.watch.processingInterval')}</Label>
                <Input id="processing-interval" className="font-mono" type="number" value={String(getVal(['watch', 'processing_interval']) ?? '')} onChange={(e) => handleChange(['watch', 'processing_interval'], parseInt(e.target.value))} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.watch.processingIntervalDesc')}</p>
              </div>
              <div>
                <Label htmlFor="idle-timeout">{t('config.watch.idleTimeout')}</Label>
                <Input id="idle-timeout" className="font-mono" type="number" value={String(getVal(['watch', 'idle_timeout']) ?? '')} onChange={(e) => handleChange(['watch', 'idle_timeout'], parseInt(e.target.value))} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.watch.idleTimeoutDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="idle-process-start">{t('config.watch.idleProcessStart')}</Label>
                <Input id="idle-process-start" className="font-mono" type="time" value={String((getVal(['watch', 'idle_process_interval']) as string[])?.[0] ?? '00:00')} onChange={(e) => {
                  const cur = (getVal(['watch', 'idle_process_interval']) as string[]) ?? ['00:00', '07:00'];
                  handleChange(['watch', 'idle_process_interval'], [e.target.value, cur[1]]);
                }} />
              </div>
              <div>
                <Label htmlFor="idle-process-end">{t('config.watch.idleProcessEnd')}</Label>
                <Input id="idle-process-end" className="font-mono" type="time" value={String((getVal(['watch', 'idle_process_interval']) as string[])?.[1] ?? '07:00')} onChange={(e) => {
                  const cur = (getVal(['watch', 'idle_process_interval']) as string[]) ?? ['00:00', '07:00'];
                  handleChange(['watch', 'idle_process_interval'], [cur[0], e.target.value]);
                }} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.watch.idleProcessDesc')}</p>
              </div>
            </div>
          </ConfigSection>

          {/* General */}
          <ConfigSection
            title={t('config.general.title')}
            description={t('config.general.description')}
            open={sectionOpen.general}
            onOpenChange={() => toggleSection('general')}
          >
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="base-dir">{t('config.general.baseDir')}</Label>
                <Input id="base-dir" className="font-mono" value={String(getVal(['base_dir']) ?? '')} onChange={(e) => handleChange(['base_dir'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.general.baseDirDesc')}</p>
              </div>
              <div>
                <Label htmlFor="screenshots-dir">{t('config.general.screenshotsDir')}</Label>
                <Input id="screenshots-dir" className="font-mono" value={String(getVal(['screenshots_dir']) ?? '')} onChange={(e) => handleChange(['screenshots_dir'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.general.screenshotsDirDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="database-path">{t('config.general.databasePath')}</Label>
                <Input id="database-path" className="font-mono" value={String(getVal(['database_path']) ?? '')} onChange={(e) => handleChange(['database_path'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.general.databasePathDesc')}</p>
              </div>
              <div>
                <Label htmlFor="default-library">{t('config.general.defaultLibrary')}</Label>
                <Input id="default-library" className="font-mono" value={String(getVal(['default_library']) ?? '')} onChange={(e) => handleChange(['default_library'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.general.defaultLibraryDesc')}</p>
              </div>
            </div>
            <div className="flex items-start space-x-2">
              <Checkbox id="facet-option" checked={!!getVal(['facet'])} onCheckedChange={() => handleChange(['facet'], !getVal(['facet']))} />
              <div className="space-y-1 leading-none">
                <Label htmlFor="facet-option">{t('config.general.enableFacet')}</Label>
                <p className="text-sm text-muted-foreground">{t('config.general.enableFacetDesc')}</p>
              </div>
            </div>
            <div className="space-y-3">
              <h4 className="text-sm font-medium">{t('config.general.defaultPlugins')}</h4>
              <div className="flex items-center space-x-2">
                <Checkbox id="builtin-ocr" checked={((getVal(['default_plugins']) as string[]) ?? []).includes('builtin_ocr')} onCheckedChange={() => {
                  const plugins = new Set((getVal(['default_plugins']) as string[]) ?? []);
                  if (plugins.has('builtin_ocr')) plugins.delete('builtin_ocr'); else plugins.add('builtin_ocr');
                  handleChange(['default_plugins'], Array.from(plugins));
                }} />
                <Label htmlFor="builtin-ocr">Builtin OCR</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox id="builtin-vlm" checked={((getVal(['default_plugins']) as string[]) ?? []).includes('builtin_vlm')} onCheckedChange={() => {
                  const plugins = new Set((getVal(['default_plugins']) as string[]) ?? []);
                  if (plugins.has('builtin_vlm')) plugins.delete('builtin_vlm'); else plugins.add('builtin_vlm');
                  handleChange(['default_plugins'], Array.from(plugins));
                }} />
                <Label htmlFor="builtin-vlm">Builtin VLM</Label>
              </div>
              <p className="text-sm text-muted-foreground">{t('config.general.defaultPluginsDesc')}</p>
            </div>
          </ConfigSection>

          {/* Server */}
          <ConfigSection
            title={t('config.server.title')}
            description={t('config.server.description')}
            open={sectionOpen.serve}
            onOpenChange={() => toggleSection('serve')}
          >
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="server-host">{t('config.server.host')}</Label>
                <Input id="server-host" className="font-mono" value={String(getVal(['server_host']) ?? '')} onChange={(e) => handleChange(['server_host'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.server.hostDesc')}</p>
              </div>
              <div>
                <Label htmlFor="server-port">{t('config.server.port')}</Label>
                <Input id="server-port" className="font-mono" type="number" value={String(getVal(['server_port']) ?? '')} onChange={(e) => handleChange(['server_port'], parseInt(e.target.value))} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.server.portDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="auth-username">{t('config.server.username')}</Label>
                <Input id="auth-username" className="font-mono" value={String(getVal(['auth_username']) ?? '')} onChange={(e) => handleChange(['auth_username'], e.target.value)} />
              </div>
              <div>
                <Label htmlFor="auth-password">{t('config.server.password')}</Label>
                <Input id="auth-password" className="font-mono" type="password" value={getVal(['auth_password']) === '********' ? '' : String(getVal(['auth_password']) ?? '')} placeholder="********" onChange={(e) => { if (e.target.value) handleChange(['auth_password'], e.target.value); }} />
              </div>
            </div>
          </ConfigSection>

          {/* Embedding */}
          <ConfigSection
            title={t('config.embedding.title')}
            description={t('config.embedding.description')}
            open={sectionOpen.embedding}
            onOpenChange={() => toggleSection('embedding')}
          >
            <Alert variant="destructive" className="border-amber-200 bg-amber-50 text-amber-700">
              <AlertDescription>
                {t('config.embedding.changeWarningPrefix', { defaultValue: 'Changing the embedding model or dimensions requires restarting services and reindexing. After changes, run ' })}
                <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-amber-800">memos reindex --force</code>
              </AlertDescription>
            </Alert>
            <div className="flex items-start space-x-2">
              <Checkbox id="use-local-embedding" checked={!!getVal(['embedding', 'use_local'])} onCheckedChange={() => handleUseLocalChange('embedding', !getVal(['embedding', 'use_local']))} />
              <Label htmlFor="use-local-embedding">{t('config.embedding.useLocal')}</Label>
            </div>
            <div className="flex items-start space-x-2">
              <Checkbox id="use-modelscope" checked={!!getVal(['embedding', 'use_modelscope'])} onCheckedChange={() => handleChange(['embedding', 'use_modelscope'], !getVal(['embedding', 'use_modelscope']))} />
              <div className="space-y-1 leading-none">
                <Label htmlFor="use-modelscope">{t('config.embedding.useModelscope')}</Label>
                <p className="text-sm text-muted-foreground">{t('config.embedding.useModelScopeDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="embedding-model">{t('config.embedding.model')}</Label>
                <Input id="embedding-model" className="font-mono" value={String(getVal(['embedding', 'model']) ?? '')} onChange={(e) => handleChange(['embedding', 'model'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.embedding.modelDesc')}</p>
              </div>
              <div>
                <Label htmlFor="embedding-dimensions">{t('config.embedding.dimensions')}</Label>
                <Input id="embedding-dimensions" className="font-mono" type="number" value={String(getVal(['embedding', 'num_dim']) ?? '')} onChange={(e) => handleChange(['embedding', 'num_dim'], parseInt(e.target.value))} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.embedding.dimensionsDesc')}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="embedding-endpoint">{t('config.embedding.endpoint')}</Label>
                <Input id="embedding-endpoint" className="font-mono" value={String(getVal(['embedding', 'endpoint']) ?? '')} disabled={uiState.inputsDisabled.embedding} onChange={(e) => handleChange(['embedding', 'endpoint'], e.target.value)} />
                <p className="mt-1 text-sm text-muted-foreground">{t('config.embedding.endpointDesc')}</p>
              </div>
              <div>
                <Label htmlFor="embedding-token">{t('config.embedding.token')}</Label>
                <Input id="embedding-token" className="font-mono" type="password" value={getVal(['embedding', 'token']) === '********' ? '' : String(getVal(['embedding', 'token']) ?? '')} placeholder="********" disabled={uiState.inputsDisabled.embedding} onChange={(e) => { if (e.target.value) handleChange(['embedding', 'token'], e.target.value); }} />
              </div>
            </div>
          </ConfigSection>
        </>
      )}
      </div>
    </div>
  );
}
