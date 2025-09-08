library(tidyverse)
library(fs)

account_dirs <- fs::dir_ls("data", type = "directory")

profile_files <- map_df(account_dirs, function(dir) {
  file <- fs::dir_ls(dir, recurse = F, type = "file", regexp = ".json.xz")
  tibble(file=file)
}) %>% 
  filter(!str_detect(file, "iterator"))

profile_infos <- map_df(profile_files$file, function(file) {
  cli::cli_alert_info("get {file}")
  profile_list <- jsonlite::read_json(file) 
  rrapply::rrapply(profile_list$node, how = "bind") %>% 
    select(-contains("iphone_struct"), -contains("lynx_url"), -contains("edge_mutual_followed_by")) %>% 
    mutate(file = file, .before = 1) %>% 
    mutate(across(everything(), as.character))
  }
) %>% 
  mutate(across(where(is.character), ~ na_if(., "NULL"))) %>% 
  as_tibble() %>% 
  mutate(across(everything(), ~ {
    if (all(. %in% c("TRUE", "FALSE"))) {
      as.logical(.)
    } else if (all(!is.na(suppressWarnings(as.integer(.))))) {
      as.integer(.)
    } else {
      .
    }
  }))
  


# export to DB ------------------------------------------------------------

con <- DBI::dbConnect(RSQLite::SQLite(), "data/instagram.sqlite")

export <- profile_infos %>% 
  mutate(created_at = Sys.time(), updated_at = NA, .before = 1)
DBI::dbWriteTable(con, "profile_infos", export, overwrite = F, append = T)
DBI::dbDisconnect(con)


