export type Category = {
  slug: string;
  name: string;
  emoji: string;
  description: string;
};

export const categories: Category[] = [
  {
    slug: 'mliecne-vyrobky',
    name: 'Mliečne výrobky',
    emoji: '🥛',
    description: 'Mlieko, jogurty, syry, smotany a maslo od slovenských spracovateľov.',
  },
  {
    slug: 'pekaren',
    name: 'Pekáreň',
    emoji: '🥐',
    description: 'Chlieb, pečivo, koláče a sladké pekárske výrobky.',
  },
  {
    slug: 'maso-a-udeniny',
    name: 'Mäso a údeniny',
    emoji: '🥓',
    description: 'Klobásy, salámy, šunky a čerstvé mäso od slovenských mäsiarov.',
  },
  {
    slug: 'ovocie-a-zelenina',
    name: 'Ovocie a zelenina',
    emoji: '🥕',
    description: 'Čerstvé i spracované ovocie a zelenina od slovenských pestovateľov.',
  },
  {
    slug: 'nealko-napoje',
    name: 'Nealko nápoje',
    emoji: '🧃',
    description: 'Limonády, džúsy a sirupy vyrábané na Slovensku.',
  },
  {
    slug: 'mineralne-vody',
    name: 'Minerálne vody',
    emoji: '💧',
    description: 'Slovenské minerálky a pramenité vody.',
  },
  {
    slug: 'pivo',
    name: 'Pivo',
    emoji: '🍺',
    description: 'Veľké pivovary i remeselné minipivovary zo Slovenska.',
  },
  {
    slug: 'vino',
    name: 'Víno',
    emoji: '🍷',
    description: 'Vína zo šiestich slovenských vinohradníckych oblastí.',
  },
  {
    slug: 'liehoviny',
    name: 'Liehoviny',
    emoji: '🥃',
    description: 'Borovičky, slivovice, hruškovice a iné slovenské destiláty.',
  },
  {
    slug: 'sladkosti-a-cokolada',
    name: 'Sladkosti a čokoláda',
    emoji: '🍫',
    description: 'Čokolády, oblátky, cukríky a tradičné sladkosti.',
  },
  {
    slug: 'slane-snacky',
    name: 'Slané snacky',
    emoji: '🥨',
    description: 'Chipsy, tyčinky, oriešky a iné slané pochúťky.',
  },
  {
    slug: 'cestoviny-ryza-muka',
    name: 'Cestoviny, ryža, múka',
    emoji: '🌾',
    description: 'Mlynské a cestovinárske výrobky od slovenských producentov.',
  },
  {
    slug: 'konzervy-a-natierky',
    name: 'Konzervy a nátierky',
    emoji: '🥫',
    description: 'Paštéty, nátierky, konzervovaná zelenina a hotové jedlá.',
  },
  {
    slug: 'koreniny-a-omacky',
    name: 'Koreniny a omáčky',
    emoji: '🧂',
    description: 'Korenia, ochucovadlá, kečupy, horčice a marinády.',
  },
  {
    slug: 'mrazene-vyrobky',
    name: 'Mrazené výrobky',
    emoji: '🧊',
    description: 'Mrazená zelenina, hotové jedlá a zmrzliny.',
  },
  {
    slug: 'drogeria-a-kozmetika',
    name: 'Drogéria a kozmetika',
    emoji: '🧴',
    description: 'Čistiace prostriedky, kozmetika a osobná hygiena.',
  },
];

export const categoryBySlug = (slug: string): Category | undefined =>
  categories.find((c) => c.slug === slug);
