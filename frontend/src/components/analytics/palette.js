// Hivemind analytics palette.
// Categorical slots 1-4 of the validated dataviz reference palette, in fixed order
// (validated against #ffffff: adjacent CVD ΔE >= 9.1; slots 1-3 also pass all-pairs,
// which is what the network uses). Aqua and yellow are below 3:1 on white, so every
// chart that uses them also has visible labels or a table view.
export const CATEGORY_ORDER = ['support', 'oppose', 'reply', 'post', 'passive']
export const INTERACTION_KINDS = ['support', 'oppose', 'reply']

export const CATEGORY_COLOR = {
  support: '#2a78d6',
  oppose: '#eb6834',
  reply: '#1baf7a',
  post: '#eda100',
  passive: '#c3c2b7'
}

// Which category each OASIS action type belongs to (mirrors the backend).
export const ACTION_CATEGORY = {
  CREATE_POST: 'post',
  LIKE_POST: 'support',
  REPOST: 'support',
  QUOTE_POST: 'support',
  LIKE_COMMENT: 'support',
  FOLLOW: 'support',
  CREATE_COMMENT: 'reply',
  DISLIKE_POST: 'oppose',
  DISLIKE_COMMENT: 'oppose',
  MUTE: 'oppose'
}

export const categoryOf = (actionType) => ACTION_CATEGORY[actionType] || 'passive'

export const INK = {
  primary: '#0b0b0b',
  secondary: '#52514e',
  muted: '#898781',
  grid: '#eeeeec',
  axis: '#c3c2b7',
  surface: '#ffffff'
}

export const fmt = (n) => (n ?? 0).toLocaleString()
export const pct = (x) => (x === null || x === undefined ? '–' : `${Math.round(x * 100)}%`)

// One colour per cast group (see backend run_briefing.GROUPS). Group names are always
// shown as text beside the colour, so colour is never the only way to tell groups apart.
export const GROUP_COLOR = {
  media: '#2a78d6',
  investors: '#1baf7a',
  government: '#eb6834',
  experts: '#8a5cd6',
  companies: '#c98a00',
  public: '#d6457f',
  organizations: '#2aa7b8',
  other: '#898781'
}
