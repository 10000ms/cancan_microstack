-- 初始化三个逻辑数据库，分别面向基础设施、运维可视化以及业务域。
-- 该脚本主要用于本地调试或一次性初始化，正式环境由 DDLManager 自动管理。

\echo 'Ensuring Cancan logical databases (infra / ops / biz)...'

DO $$
BEGIN
	IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'infra') THEN
		EXECUTE 'CREATE DATABASE infra WITH ENCODING ''UTF8'' TEMPLATE template0 LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8''';
	END IF;

	IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ops') THEN
		EXECUTE 'CREATE DATABASE ops WITH ENCODING ''UTF8'' TEMPLATE template0 LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8''';
	END IF;

	IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'biz') THEN
		EXECUTE 'CREATE DATABASE biz WITH ENCODING ''UTF8'' TEMPLATE template0 LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8''';
	END IF;
END;
$$;

\connect infra;