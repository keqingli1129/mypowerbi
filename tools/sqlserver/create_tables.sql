/*
Step 13a: database FMCG, schema fmcg and the 10 tables Power BI reads (docs/sqlserver_onprem_guide.md).

Same table and column names as the Databricks tables (snake_case, see snake() in tools/fmcg_data.py),
so the model's sourceColumn lines work for both sources. Money columns are DECIMAL(18, 2): the model
stores them as decimal, and no value has more than 2 real decimal places.

Safe to run again: it only creates what doesn't exist yet and never drops or changes data.
Run from the repo root (local SQL Server Express, Windows sign-in):
    sqlcmd -S .\SQLEXPRESS -E -C -b -i tools/sqlserver/create_tables.sql
*/

IF DB_ID(N'FMCG') IS NULL
    CREATE DATABASE FMCG;
GO

USE FMCG;
GO

-- CREATE SCHEMA must be alone in its batch, hence EXEC
IF SCHEMA_ID(N'fmcg') IS NULL
    EXEC (N'CREATE SCHEMA fmcg');
GO

-- Dimensions -----------------------------------------------------------------------------------

IF OBJECT_ID(N'fmcg.[date]', N'U') IS NULL
CREATE TABLE fmcg.[date] (
    [date]            DATE          NOT NULL PRIMARY KEY,
    [year]            BIGINT        NOT NULL,
    month_number      BIGINT        NOT NULL,
    year_month_number BIGINT        NOT NULL,
    month_name        NVARCHAR(100) NOT NULL,
    [month]           NVARCHAR(100) NOT NULL,
    [quarter]         NVARCHAR(100) NOT NULL,
    financial_year    NVARCHAR(100) NOT NULL
);

IF OBJECT_ID(N'fmcg.area', N'U') IS NULL
CREATE TABLE fmcg.area (
    zone NVARCHAR(100) NOT NULL,
    rsm  NVARCHAR(100) NOT NULL,
    asm  NVARCHAR(100) NOT NULL PRIMARY KEY
);

IF OBJECT_ID(N'fmcg.sales_officer', N'U') IS NULL
CREATE TABLE fmcg.sales_officer (
    sales_officer NVARCHAR(100) NOT NULL PRIMARY KEY,
    asm           NVARCHAR(100) NOT NULL
);

IF OBJECT_ID(N'fmcg.distributor', N'U') IS NULL
CREATE TABLE fmcg.distributor (
    distributor_code NVARCHAR(100) NOT NULL PRIMARY KEY,
    distributor      NVARCHAR(100) NOT NULL,
    [state]          NVARCHAR(100) NOT NULL,
    city             NVARCHAR(100) NOT NULL
);

IF OBJECT_ID(N'fmcg.category', N'U') IS NULL
CREATE TABLE fmcg.category (
    category NVARCHAR(100) NOT NULL PRIMARY KEY
);

IF OBJECT_ID(N'fmcg.product', N'U') IS NULL
CREATE TABLE fmcg.product (
    sku_code       NVARCHAR(100)  NOT NULL PRIMARY KEY,
    brand          NVARCHAR(100)  NOT NULL,
    sku            NVARCHAR(100)  NOT NULL,
    pack           NVARCHAR(100)  NOT NULL,
    mrp            DECIMAL(18, 2) NOT NULL,
    units_per_case BIGINT         NOT NULL,
    ptr            DECIMAL(18, 2) NOT NULL,
    pts            DECIMAL(18, 2) NOT NULL
);

-- Facts ----------------------------------------------------------------------------------------

IF OBJECT_ID(N'fmcg.primary_sales', N'U') IS NULL
CREATE TABLE fmcg.primary_sales (
    [date]            DATE           NOT NULL,
    asm               NVARCHAR(100)  NOT NULL,
    sales_officer     NVARCHAR(100)  NOT NULL,
    category          NVARCHAR(100)  NOT NULL,
    distributor_code  NVARCHAR(100)  NOT NULL,
    sku_code          NVARCHAR(100)  NOT NULL,
    units             BIGINT         NOT NULL,
    gross_value       DECIMAL(18, 2) NOT NULL,
    scheme_discount   DECIMAL(18, 2) NOT NULL,
    net_primary_value DECIMAL(18, 2) NOT NULL
);

IF OBJECT_ID(N'fmcg.secondary_sales', N'U') IS NULL
CREATE TABLE fmcg.secondary_sales (
    [date]           DATE           NOT NULL,
    asm              NVARCHAR(100)  NOT NULL,
    sales_officer    NVARCHAR(100)  NOT NULL,
    category         NVARCHAR(100)  NOT NULL,
    distributor_code NVARCHAR(100)  NOT NULL,
    sku_code         NVARCHAR(100)  NOT NULL,
    channel          NVARCHAR(100)  NOT NULL,
    units_sold       BIGINT         NOT NULL,
    secondary_value  DECIMAL(18, 2) NOT NULL
);

IF OBJECT_ID(N'fmcg.targets', N'U') IS NULL
CREATE TABLE fmcg.targets (
    [date]                 DATE          NOT NULL,
    asm                    NVARCHAR(100) NOT NULL,
    category               NVARCHAR(100) NOT NULL,
    primary_target_value   BIGINT        NOT NULL,
    secondary_target_value BIGINT        NOT NULL
);

IF OBJECT_ID(N'fmcg.coverage', N'U') IS NULL
CREATE TABLE fmcg.coverage (
    [date]           DATE           NOT NULL,
    asm              NVARCHAR(100)  NOT NULL,
    sales_officer    NVARCHAR(100)  NOT NULL,
    total_outlets    BIGINT         NOT NULL,
    outlets_billed   BIGINT         NOT NULL,
    planned_calls    BIGINT         NOT NULL,
    productive_calls BIGINT         NOT NULL,
    lines_per_bill   DECIMAL(18, 2) NOT NULL
);
GO

-- Show what exists now
SELECT t.name AS table_name, COUNT(c.column_id) AS columns
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id = t.object_id
WHERE t.schema_id = SCHEMA_ID(N'fmcg')
GROUP BY t.name
ORDER BY t.name;
GO
