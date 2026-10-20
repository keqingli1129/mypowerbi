/*
Step 13e (part 1): read-only SQL login for the Power BI gateway (docs/sqlserver_onprem_guide.md, step 1).

The gateway connection in the Power BI Service stores this login's password and uses it for every
scheduled refresh. Least privilege: it can only SELECT from schema fmcg, nothing else.

Needs "SQL Server and Windows Authentication mode" (SERVERPROPERTY('IsIntegratedSecurityOnly') = 0).
The password never goes into this file: sqlcmd fills $(ReaderPassword) from an environment variable
of the same name. In PowerShell, from the repo root:

    $env:ReaderPassword = [Net.NetworkCredential]::new('', (Read-Host 'Password for powerbi_reader' -AsSecureString)).Password
    sqlcmd -S .\SQLEXPRESS -E -C -b -i tools/sqlserver/create_reader.sql
    Remove-Item Env:ReaderPassword

Safe to run again: it only creates what doesn't exist yet (it doesn't change an existing password).
*/

:on error exit

USE master;
IF SUSER_ID(N'powerbi_reader') IS NULL
    CREATE LOGIN powerbi_reader WITH PASSWORD = N'$(ReaderPassword)',
        DEFAULT_DATABASE = FMCG, CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;
GO

USE FMCG;
IF USER_ID(N'powerbi_reader') IS NULL
    CREATE USER powerbi_reader FOR LOGIN powerbi_reader;
GRANT SELECT ON SCHEMA::fmcg TO powerbi_reader;
GO

-- Show what the login may do in FMCG
SELECT p.permission_name, p.state_desc, p.class_desc, SCHEMA_NAME(p.major_id) AS schema_name
FROM sys.database_permissions AS p
WHERE p.grantee_principal_id = USER_ID(N'powerbi_reader') AND p.class_desc = N'SCHEMA';
GO
