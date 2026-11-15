import { integer, sqliteTable, text, index } from 'drizzle-orm/sqlite-core';
export const requests=sqliteTable('requests',{
 id:text('id').primaryKey(),owner:text('owner').notNull(),path:text('path').notNull(),method:text('method').notNull(),payload:text('payload').notNull(),status:text('status').notNull(),result:text('result'),created:integer('created').notNull(),claimed:integer('claimed'),lease:text('lease')
},table=>[index('requests_owner_created').on(table.owner,table.created),index('requests_status_created').on(table.status,table.created)]);
export const workers=sqliteTable('workers',{id:text('id').primaryKey(),seen:integer('seen').notNull()});
