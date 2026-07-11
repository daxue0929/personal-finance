---
name: "project-naming-convention"
description: "Ensures code follows project naming conventions for files, classes, methods, and variables. Invoke when user modifies code, creates new files/classes, or asks about naming standards. Automatically applies to storage, database, and all module modifications."
---

# Project Naming Convention

## Overview

This skill documents the naming conventions used in the personal-finance data-crawler project.

## File Naming

- **Format**: lowercase_with_underscores.py
- **Example**: `fund_info_storage.py`, `task_schedule_storage.py`
- **Storage files**: End with `_storage.py`

## Class Naming

| Type | Format | Example |
|------|--------|---------|
| Database Entity | PascalCase (same as table name) | `FundInfo`, `TaskSchedule` |
| Storage/Operation | EntityName + Storage | `FundInfoStorage`, `TaskScheduleStorage` |

## Method/Function Naming

- **Format**: lowercase_with_underscores
- **Example**: `get_all_fund_codes()`, `update_fund_net_value()`
- **Prefix conventions**:
  - `get_` - Retrieve data
  - `update_` - Modify existing data
  - `create_` - Create new data
  - `delete_` - Remove data
  - `batch_` - Batch operations
  - `_private_method` - Internal use only

## Variable Naming

- **Format**: lowercase_with_underscores
- **Example**: `fund_code`, `net_asset_value`, `task_storage`

## Directory Structure

```
app/
├── parser/          # Data parsing layer
├── storage/         # Data storage layer (models + operations)
├── scheduler/       # Task scheduling layer
├── task/            # Task implementations
├── utils/           # Utility functions
└── web/             # Web service layer
```

## Module-Specific Naming Conventions

### Storage Module (`storage/`)
- **File**: `<entity>_storage.py` (e.g., `fund_info_storage.py`)
- **Entity Class**: `<EntityName>` (e.g., `FundInfo`)
- **Storage Class**: `<EntityName>Storage` (e.g., `FundInfoStorage`)
- **Methods**: `get_*`, `update_*`, `create_*`, `delete_*`, `batch_*`

### Parser Module (`parser/`)
- **File**: `<parser_name>_parser.py` (e.g., `fund_parser.py`)
- **Class**: `<ParserName>Parser` (e.g., `FundParser`)
- **Methods**: `fetch()`, `parse()`, `fetch_multiple_*()`

### Task Module (`task/`)
- **File**: `<task_name>_task.py` (e.g., `update_fund_net_values_task.py`)
- **Function**: `<task_name>_task()` (e.g., `update_fund_net_values_task()`)

### Scheduler Module (`scheduler/`)
- **File**: `<scheduler_type>_scheduler.py` (e.g., `cron_scheduler.py`)
- **Class**: `<SchedulerType>Scheduler` (e.g., `CronTaskScheduler`)

### Utils Module (`utils/`)
- **File**: `<utility_name>_utils.py` (e.g., `datetime_utils.py`)
- **Functions**: `<utility_function>()` (e.g., `get_beijing_now()`)

### Web Module (`web/`)
- **File**: `<api_name>.py` (e.g., `api_server.py`)
- **Class**: Flask app instance named `app`
- **Routes**: `/api/<resource>` pattern

## Import Conventions

- Absolute imports preferred for cross-module references
- Relative imports for same-package references
- Example: `from ..storage import FundInfoStorage`

## Database Table Naming

- **Format**: snake_case
- **Example**: `fund_info`, `task_schedule`
- **Relationship**: Table name = lowercase entity class name

## Example Implementation

```python
# File: fund_info_storage.py

class FundInfo(Base):
    __tablename__ = 'fund_info'  # Table name matches entity name
    fund_code = Column(String(10))

class FundInfoStorage:
    def get_fund_by_code(self, fund_code: str):
        # Implementation
        pass
```

## Best Practices

1. Be consistent throughout the project
2. Use descriptive names that reflect purpose
3. Avoid abbreviations unless universally understood
4. Follow Python PEP 8 guidelines
5. Match class names with database table names