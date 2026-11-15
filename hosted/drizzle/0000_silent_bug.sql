CREATE TABLE `requests` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`path` text NOT NULL,
	`method` text NOT NULL,
	`payload` text NOT NULL,
	`status` text NOT NULL,
	`result` text,
	`created` integer NOT NULL,
	`claimed` integer,
	`lease` text
);
--> statement-breakpoint
CREATE INDEX `requests_owner_created` ON `requests` (`owner`,`created`);--> statement-breakpoint
CREATE INDEX `requests_status_created` ON `requests` (`status`,`created`);--> statement-breakpoint
CREATE TABLE `workers` (
	`id` text PRIMARY KEY NOT NULL,
	`seen` integer NOT NULL
);
