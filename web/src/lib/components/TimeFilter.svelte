<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { RangeCalendar } from '$lib/components/ui/range-calendar/index.js';
	import { _ } from 'svelte-i18n';

	import {
		type DateValue,
		getLocalTimeZone
	} from '@internationalized/date';

	let now = +new Date();

	// rangeMap now only holds start/end values; label is derived via getLabel()
	let rangeMap: {
		[key: string]: {
			start: number | null;
			end: number | null;
		};
	} = $state({
		unlimited: {
			start: null,
			end: null
		},
		threeHours: {
			start: now - 3 * 60 * 60 * 1000,
			end: now
		},
		today: {
			start: now - 24 * 60 * 60 * 1000,
			end: now
		},
		week: {
			start: now - 7 * 24 * 60 * 60 * 1000,
			end: now
		},
		month: {
			start: now - 30 * 24 * 60 * 60 * 1000,
			end: now
		},
		threeMonths: {
			start: now - 90 * 24 * 60 * 60 * 1000,
			end: now
		},
		custom: {
			start: null,
			end: null
		}
	});

	let timeFilter = $state('unlimited');
	interface Props {
		start: number;
		end: number;
	}

	let { start = $bindable(), end = $bindable() }: Props = $props();

	let customDateRange: { start: DateValue | null; end: DateValue | null } = $state({
		start: null,
		end: null
	});

	// function to get localized label text for each key
	function getLabel(key: string) {
		switch (key) {
			case 'unlimited': return $_('timeFilter.unlimited');
			case 'threeHours': return $_('timeFilter.threeHours');
			case 'today': return $_('timeFilter.today');
			case 'week': return $_('timeFilter.week');
			case 'month': return $_('timeFilter.month');
			case 'threeMonths': return $_('timeFilter.threeMonths');
			case 'custom': return $_('timeFilter.custom');
			default: return '';
		}
	}

	let displayText =
		$derived((timeFilter === 'custom' && customDateRange.start && customDateRange.end)
			? $_('timeFilter.customRange', { values: { start: customDateRange.start?.toString(), end: customDateRange.end?.toString() } })
			: getLabel(timeFilter));

	// Only sync customDateRange to rangeMap.custom when timeFilter is 'custom'
	$effect(() => {
		if (timeFilter === 'custom' && customDateRange.start && customDateRange.end) {
			rangeMap.custom.start = customDateRange.start.toDate(getLocalTimeZone()).getTime();
			rangeMap.custom.end = customDateRange.end.toDate(getLocalTimeZone()).getTime();
		}
	});

	// When timeFilter is changed to anything other than 'custom', clear customDateRange
	$effect(() => {
		if (timeFilter !== 'custom') {
			customDateRange = { start: null, end: null };
		}
	});

	// Automatically update start and end props based on timeFilter and rangeMap
	$effect(() => {
		if (
			timeFilter === 'custom' &&
			rangeMap.custom.start !== null &&
			rangeMap.custom.end !== null
		) {
			start = rangeMap.custom.start;
			end = rangeMap.custom.end;
		} else if (timeFilter !== 'custom') {
			start = rangeMap[timeFilter].start!;
			end = rangeMap[timeFilter].end!;
		}
	});

	// Automatically switch to 'custom' filter when user selects a valid customDateRange
	$effect(() => {
		if (
			customDateRange.start &&
			customDateRange.end &&
			timeFilter !== 'custom'
		) {
			timeFilter = 'custom';
		}
	});
</script>

<div>
	<DropdownMenu.Root>
		<DropdownMenu.Trigger>
			<Button
				variant="outline"
				size="sm"
				class="border p-2 text-xs font-medium focus:outline-none"
			>
				<span class="truncate">{displayText}</span>
			</Button>
		</DropdownMenu.Trigger>
		<DropdownMenu.Content class="w-56" align="start" side="bottom">
			<DropdownMenu.Label>{$_('timeFilter.label')}</DropdownMenu.Label>
			<DropdownMenu.Separator />
			<DropdownMenu.RadioGroup bind:value={timeFilter}>
				<DropdownMenu.RadioItem value="unlimited">{getLabel('unlimited')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="threeHours">{getLabel('threeHours')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="today">{getLabel('today')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="week">{getLabel('week')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="month">{getLabel('month')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="threeMonths">{getLabel('threeMonths')}</DropdownMenu.RadioItem>
				<DropdownMenu.Sub>
					<DropdownMenu.SubTrigger>{getLabel('custom')}</DropdownMenu.SubTrigger>
					<DropdownMenu.SubContent>
						<RangeCalendar bind:value={customDateRange} />
					</DropdownMenu.SubContent>
				</DropdownMenu.Sub>
			</DropdownMenu.RadioGroup>
		</DropdownMenu.Content>
	</DropdownMenu.Root>
</div>
