---
name: "stored-procedure-executor"
description: "Executes stored procedure SQL files to MySQL database. Invoke when user asks to execute, run, or deploy stored procedures to the database."
---

# Stored Procedure Executor

## Overview

This skill provides automated execution of stored procedure SQL files to the MySQL database in the personal-finance project. It handles DELIMITER commands and ensures safe, repeatable execution.

## When to Invoke

Invoke this skill when:
- User asks to execute stored procedure SQL files
- User asks to run SQL files to update database procedures
- User asks to deploy stored procedures to database
- After modifying stored procedure files that need to be applied to database

## Workflow

### Execute Single Stored Procedure File

1. **Prepare SQL file** (ensure proper DELIMITER syntax)
2. **Execute via MySQL CLI**
```bash
mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < /path/to/procedure.sql
```

### Execute Multiple Stored Procedures

```bash
# Execute all SQL files in program directory
for file in /Users/wangxuedi/open_source/personal-finance/sql/program/*.sql; do
    echo "Executing: $file"
    mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < "$file"
done
```

## Configuration

Database connection parameters should be configured via environment variables or configuration files:

| Parameter | Environment Variable | Description |
|----------|---------------------|-------------|
| Host | DB_HOST | Database server hostname |
| Port | DB_PORT | Database server port |
| User | DB_USER | Database username |
| Password | DB_PASSWORD | Database password |
| Database | DB_NAME | Database name |

## Important Notes

- **DELIMITER Handling**: MySQL CLI automatically handles DELIMITER commands in .sql files
- **Idempotency**: Use `DROP PROCEDURE IF EXISTS` before `CREATE PROCEDURE` for safe re-execution
- **Error Handling**: If execution fails, check SQL syntax and database connection
- **Backup**: Consider backing up the database before executing major changes
- **Permissions**: Ensure the database user has CREATE ROUTINE and ALTER ROUTINE privileges
- **Security**: Never hardcode passwords in scripts or documentation; use environment variables or secure vaults

## Complete Examples

### Execute Single File
```bash
mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < /Users/wangxuedi/open_source/personal-finance/sql/program/基金历史净值.sql
```

### Execute Buy Procedure
```bash
mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < /Users/wangxuedi/open_source/personal-finance/sql/program/买入.sql
```

### Verify Procedure Exists
```bash
mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SHOW PROCEDURE STATUS WHERE Db = '${DB_NAME}';"
```

### Test Procedure Execution
```bash
mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "CALL backup_fund_nav_history();"
```

## SQL File Requirements

Stored procedure SQL files should follow this structure:

```sql
DELIMITER $$

DROP PROCEDURE IF EXISTS `procedure_name`$$

CREATE PROCEDURE `procedure_name`()
BEGIN
    -- Procedure logic here
END$$

DELIMITER ;
```

## Troubleshooting

- **DELIMITER Errors**: Ensure DELIMITER commands are properly formatted
- **Permission Denied**: Verify user credentials and host access
- **Syntax Errors**: Check SQL syntax, especially around DECLARE statements (must be first in BEGIN block)
- **Timezone Issues**: Set timezone inside procedure with `SET SESSION time_zone = 'Asia/Shanghai';`
