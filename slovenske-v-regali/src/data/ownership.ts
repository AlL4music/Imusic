export type OwnershipKey =
  | 'slovak'
  | 'made-in-sk-foreign-owned'
  | 'slovak-brand-made-abroad';

export type OwnershipInfo = {
  key: OwnershipKey;
  emoji: string;
  short: string;
  label: string;
  className: string;
};

export const OWNERSHIP: Record<OwnershipKey, OwnershipInfo> = {
  slovak: {
    key: 'slovak',
    emoji: '🇸🇰',
    short: 'Slovenská značka',
    label: 'Slovenská značka, slovenský vlastník, vyrobené na Slovensku',
    className: 'badge-slovak',
  },
  'made-in-sk-foreign-owned': {
    key: 'made-in-sk-foreign-owned',
    emoji: '🏭',
    short: 'Vyrobené na Slovensku',
    label: 'Vyrobené na Slovensku, zahraničný vlastník',
    className: 'badge-made',
  },
  'slovak-brand-made-abroad': {
    key: 'slovak-brand-made-abroad',
    emoji: '📦',
    short: 'Slovenská značka, vyrobené v zahraničí',
    label: 'Slovenská značka, vyrobené v zahraničí',
    className: 'badge-abroad',
  },
};
