library(tidyverse)
library(fs)
library(glue)
library(lubridate)
library(DBI)
library(testdat)

source(here::here("code/get-connection-functions.R"))

OUTPUT_DIR <- here::here("data")

account_tbl <- "archive_account"
account_cats_tbl <- "account_cats"
posts_metadata_tbl <- "archive_files_metadata"
posts_tbl <- "archive_files"
connections_tbl <- "archive_connections"

year_regex <- "20[0-9]{2}$"
file_ext_regex <- "json.xz"

con <- DBI::dbConnect(RSQLite::SQLite(), here::here("data/instagram.sqlite"))

find_shortcode <- function(path) {
  
  shortcode_regex <- "([^\\/]+)_[\\d]{4}-[\\d]{2}-[\\d]{2}_[\\d]{2}-[\\d]{2}-[\\d]{2}_UTC_comments\\.json$"
  #shortcode_regex <- "(.*?)(_20[\\d]{2}-[\\d]{2}-[\\d]{2}_[\\d]{2}-[\\d]{2}-[\\d]{2}_UTC(_comments)?\\.json)$"
  
  # Extract and replace the shortcode
  shortcode <- str_extract(path, shortcode_regex) %>%
    str_replace(shortcode_regex, "\\1")
  
  # # Check the length of the extracted shortcode and truncate if necessary
  # if (nchar(shortcode) > 11) {
  #   shortcode <- str_split(shortcode, "_")[[1]][1]
  # }
  
  return(shortcode)
}

# connections_export %>% filter(!nchar(shortcode) %in% c(10, 11, NA))  %>%
#   mutate(s2 = str_extract(shortcode, "_+")) %>% select(shortcode, s2)
# 
# find_shortcode("DK93l3ZIVb7c96tOVxRCDbl6D7PDjiue130Z6Q0")
