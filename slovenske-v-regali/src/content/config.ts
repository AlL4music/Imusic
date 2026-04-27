import { defineCollection, z } from 'astro:content';
import { categories } from '../data/categories';

const categorySlugs = categories.map((c) => c.slug) as [string, ...string[]];

const brands = defineCollection({
  type: 'content',
  schema: z.object({
    name: z.string(),
    category: z.enum(categorySlugs),
    ownership: z.enum([
      'slovak',
      'made-in-sk-foreign-owned',
      'slovak-brand-made-abroad',
    ]),
    website: z.string().url().optional(),
    region: z.string().optional(),
    founded: z.number().int().optional(),
    logo: z.string().optional(),
    featured: z.boolean().optional().default(false),
  }),
});

export const collections = { brands };
