# 1. Create a Resource Group
resource "azurerm_resource_group" "rg" {
    name = "${var.project_name}-rg"
    location = var.location
}

# 2. Create a Storage Account (Data Lake)
resource "azurerm_storage_account" "datalake" {
    name = "${var.project_name}datalake"
    resource_group_name = azurerm_resource_group.rg.name
    location = azurerm_resource_group.rg.location
    account_tier = "Standard"
    account_replication_type = "LRS"
}

# 3. Create a Blob Container (Folder for raw data)
resource "azurerm_storage_container" "raw_data" {
    name = "raw-parquet-chunks"
    storage_account_name = azurerm_storage_account.datalake.name
    container_access_type = "private"

}
