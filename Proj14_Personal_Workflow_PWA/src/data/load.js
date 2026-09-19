import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const TEMPLATE_URL = new URL('./schedule-template.json', import.meta.url);

export function loadTemplate() {
  return JSON.parse(readFileSync(fileURLToPath(TEMPLATE_URL), 'utf8'));
}

const CAMPAIGN_URL = new URL('./campaign-talk-demo.json', import.meta.url);

export function loadCampaign() {
  return JSON.parse(readFileSync(fileURLToPath(CAMPAIGN_URL), 'utf8'));
}
