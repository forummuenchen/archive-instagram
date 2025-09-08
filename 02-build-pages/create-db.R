library(tidyverse)
library(fs)
library(glue)
library(lubridate)
library(DBI)
library(testdat)

source(here::here("code/get-connection-functions.R"))
source(here::here("code/setup.R"))

OUTPUT_DIR <- "data"


delete_db <- FALSE


extract_profiles_again <- FALSE

if (extract_profiles_again == TRUE) {
  source(here::here("code/extract-profile-infos.R"))
}

# setup db tables ---------------------------------------------------------


if(delete_db == T) {
  DBI::dbRemoveTable(con, account_tbl)
  DBI::dbRemoveTable(con, posts_metadata_tbl)
  DBI::dbRemoveTable(con, posts_tbl)
  DBI::dbRemoveTable(con, connections_tbl)
}

#DBI::dbRemoveTable(con, account_tbl)
create_account <- glue("CREATE TABLE IF NOT EXISTS {account_tbl} (
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT NULL,
  source TEXT PRIMARY KEY,
  id INTEGER,
  username TEXT,
  full_name TEXT,
  biography TEXT,
  is_private BOOLEAN,
  is_verified BOOLEAN,
  follows INTEGER,
  follower INTEGER,
  fb_profile_biolink TEXT,
  external_url TEXT,
  category_name TEXT,
  is_business_account BOOLEAN,
  is_professional_account BOOLEAN,
  business_address_json JSON,
  last_update TEXT,
  br_category TEXT
  )")
dbExecute(con, create_account)

#DBI::dbRemoveTable(con, posts_metadata_tbl)
create_posts_metadata <- glue("CREATE TABLE IF NOT EXISTS {posts_metadata_tbl} (
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT NULL,
  type TEXT,
  shortcode TEXT,
  downloaded_at INTEGER,
  username TEXT,
  dir TEXT,
  year INTEGER,
  file TEXT,
  path TEXT,
  CONSTRAINT PK_post PRIMARY KEY (path, shortcode, type)
  )")
dbExecute(con, create_posts_metadata)

#DBI::dbRemoveTable(con, posts_tbl)
create_posts <- glue("CREATE TABLE IF NOT EXISTS {posts_tbl} (
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT NULL,
  path TEXT,
  type TEXT,
  shortcode TEXT,
  timestamp INTEGER,
  date TEXT,
  is_story BOOLEAN,
  reel_id TEXT,
  expiring_at INTEGER,
  expiring_at_date TEXT,
  accessibility_caption TEXT,
  caption TEXT,
  like_count INTEGER,
  comments_count INTEGER,
  location_name TEXT,
  story_link TEXT,
  music_artist TEXT,
  music_song TEXT
  )")
dbExecute(con, create_posts)


#DBI::dbRemoveTable(con, connections_tbl)
create_connections <- glue("CREATE TABLE IF NOT EXISTS {connections_tbl} (
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT NULL,
  user_in_focus TEXT,
  username TEXT,
  type TEXT,
  path TEXT,
  shortcode TEXT,
  reel_id TEXT,
  text TEXT
  )")
dbExecute(con, create_connections)

# account data ------------------------------------------------------------

if (delete_db != TRUE) {
  accounts_in_db <- tbl(con, account_tbl) %>% distinct(username) %>% collect()  
} else {
  accounts_in_db <- NULL
}


account_cats <- tbl(con, account_cats_tbl) %>% collect() %>% 
  reframe(br_category = glue::glue_collapse(type, sep = ", "), .by = username)

account_dirs <- fs::dir_ls("data", type = "directory")

account_files <- map_df(account_dirs, function(dir) {
  file <- fs::dir_ls(dir, recurse = F, type = "file", regexp = file_ext_regex)
  tibble(file = file)
}) %>%
  filter(!str_detect(file, "iterator|#"))

if(length(accounts_in_db$username) > 0 ) {
  account_files <- account_files %>% 
    filter(!str_detect(file, paste0(accounts_in_db$username, collapse = "|")))
}
  

if (nrow(account_files) > 0) {
  account_infos <- map_df(account_files$file, function(file) {
    cli::cli_alert_info("get {file}")
    account_list <- jsonlite::read_json(file)
    rrapply::rrapply(account_list$node, how = "bind") %>%
      select(-contains("iphone_struct"), -contains("lynx_url"), -contains("edge_mutual_followed_by")) %>%
      mutate(file = file, .before = 1) %>%
      mutate(across(everything(), as.character))
  }) %>%
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
  
  account_export <- account_infos %>%
    select(source = file, 
           id, 
           username, 
           full_name, 
           biography, 
           is_private, 
           is_verified, 
           follows = edge_follow.count, 
           follower = edge_followed_by.count, 
           fb_profile_biolink, 
           external_url, 
           is_business_account,
           is_professional_account,
           category_name,
           business_address_json) %>% 
    left_join(account_cats, by = join_by(username)) %>% 
    mutate(br_category = ifelse(is.na(br_category), "", br_category))
  
  test_that(
    desc = "unique row for username",
    expect_unique(vars = username, data = account_export)
  )
}



# files meta data ---------------------------------------------------------

all_account_sub_dirs <- fs::dir_ls(account_dirs, type = "directory")

post_dirs <- fs::dir_ls(account_dirs, type = "directory", regexp = glue("/{year_regex}"))


post_files <- map_df(post_dirs, function(dir) {
  file <- fs::dir_ls(dir, type = "file", regexp = file_ext_regex, recurse = F)
  tibble(file = file)
}) %>%
  filter(!str_detect(file, "iterator|#"))


# get tagged files --------------------------------------------------------

tagged_dirs <- fs::dir_ls(account_dirs, type = "directory", regexp = "tagged")

tagged_files <- map_df(tagged_dirs, function(dir) {
  file <- fs::dir_ls(dir, type = "file", regexp = file_ext_regex, recurse = T)
  tibble(file = file)
}) %>%
  filter(!str_detect(file, "iterator|#"))

# get story files --------------------------------------------------------

story_dirs <- fs::dir_ls(account_dirs, type = "directory", regexp = "STORY")

story_files <- map_df(story_dirs, function(dir) {
  file <- fs::dir_ls(dir, type = "file", regexp = file_ext_regex, recurse = T)
  tibble(file = file)
}) 

if (nrow(story_files) > 0) {
  story_files <- story_files %>%
    filter(!str_detect(file, "iterator|#"))
}


# get highlight files -----------------------------------------------------

# all the rest
highlight_dirs <- enframe(all_account_sub_dirs) %>%
  select(value) %>%
  anti_join(enframe(post_dirs) %>% select(value), by = join_by(value)) %>%
  anti_join(enframe(tagged_dirs) %>% select(value), by = join_by(value)) %>%
  anti_join(enframe(story_dirs) %>% select(value), by = join_by(value)) %>%
  pull(value)


highlight_files <- map_df(highlight_dirs, function(dir) {
  file <- fs::dir_ls(dir, type = "file", regexp = file_ext_regex, recurse = T)
  tibble(file = file)
}) %>%
  filter(!str_detect(file, "iterator|#"))


get_files_meta_data <- function(data, type = NULL) {
  tmp <- data %>%
    rowid_to_column() %>%
    separate_rows(file, sep = "/") %>%
    mutate(file = trimws(file)) %>%
    filter(file != OUTPUT_DIR) %>%
    group_by(rowid) %>%
    mutate(
      type =
        case_when(
          row_number() == 1 ~ "username",
          str_detect(file, glue("^{year_regex}")) ~ "year",
          str_detect(file, file_ext_regex) ~ "file",
          TRUE ~ "dir"
        )
    ) %>%
    ungroup() %>%
    pivot_wider(id_cols = rowid, names_from = type, values_from = file) %>%
    mutate(
      across(everything(), as.character),
      year = as.numeric(year),
      type = type,
      shortcode = str_remove(str_extract(file, ".*_20"), "_20"), 
      #shortcode = str_sub(shortcode, 1, 11), .before = 1 #str_extract(file, "20[0-9]{2}/.+") %>% str_extract(., "/.+") %>% str_sub(2, 12), .before = 1#
    ) %>%
    select(-rowid)

  if (type == "post") {
    tmp <- tmp %>%
      mutate(path = fs::path(OUTPUT_DIR, username, year, file)) %>%
      mutate(dir = "post", .after = username)
  } else {
    tmp <- tmp %>%
      mutate(path = fs::path(OUTPUT_DIR, username, dir, year, file))
  }
  downloaded_at <- tmp %>%
    select(path) %>%
    mutate(dw_date = fs::file_info(path)) %>% 
    select(-path) %>% 
    unnest(dw_date) %>% 
    select(path, downloaded_at = birth_time)
  

  tmp <- tmp %>% 
    left_join(downloaded_at, by = join_by(path)) %>% 
    distinct()
   
}

cli::cli_alert_info("create files meta data table")

if(nrow(story_files) > 0) {
  posts_metadata_export <- bind_rows(
    get_files_meta_data(highlight_files, type = "highlight"),
    get_files_meta_data(post_files, type = "post"),
    get_files_meta_data(story_files, type = "story"),
    get_files_meta_data(tagged_files, type = "tagged")
  ) %>% 
    filter(!is.na(path))
} else {
  posts_metadata_export <- bind_rows(
    get_files_meta_data(highlight_files, type = "highlight"),
    get_files_meta_data(post_files, type = "post"),
    #get_files_meta_data(story_files, type = "story"),
    get_files_meta_data(tagged_files, type = "tagged")
  ) %>% 
    filter(!is.na(path))
}

# testthat::test_that(
#   desc = "shortcode has 9 chars",
#   expect_equal(
#     posts_metadata_export %>% filter(!nchar(shortcode) %in% c(11, 10)) %>% nrow(), 0
#   )
# )

testthat::test_that(
  desc = "unique",
  expect_unique(c(path, type), data = posts_metadata_export)
)

already_in_db <- tbl(con, posts_metadata_tbl) %>% distinct(path) %>% collect()
DBI::dbWriteTable(con, posts_metadata_tbl, posts_metadata_export %>% anti_join(already_in_db, by = join_by(path)), append = T)
cli::cli_alert_success("files meta data written")




# write accounts tbl to db, incl last_update ------------------------------

last_update <- posts_metadata_export %>% 
  group_by(username) %>% 
  filter(downloaded_at == max(downloaded_at)) %>% 
  distinct(username, last_update = downloaded_at) %>% 
  mutate(last_update = as_date(last_update) %>% as.character())

if (exists("account_export") == TRUE) {
  if(extract_profiles_again == FALSE) {
    DBI::dbWriteTable(con, 
                      account_tbl, 
                      account_export %>% 
                        left_join(last_update, by = join_by(username)), append = T)
  } else {
    DBI::dbWriteTable(con, 
                      account_tbl, 
                      account_export %>% 
                        left_join(last_update, by = join_by(username)) %>% 
                        anti_join(accounts_in_db, by = join_by(username)), append = T)
  }

}



# post data ---------------------------------------------------------------

posts_in_db <- tbl(con, posts_tbl) %>% distinct(path) %>% collect()

posts_export <- posts_metadata_export %>% 
  anti_join(posts_in_db, by = join_by(path)) %>% 
  #head(1) %>% 
    pmap_df(function(...) {
      current <- tibble(...)
      path <- current$path
      type <- current$type
      shortcode <- current$shortcode
      
      cli::cli_alert_info("{path}")
      
      if(fs::file_exists(path)) {
        
      json <- jsonlite::read_json(path)
      #json <- jsonlite::read_json("data/13.ms12/L😝❤️/2025/DK-peO8N636_2025-06-16_22-43-53_UTC.json.xz")
      
      timestamp <- ifelse(
        length(json[["node"]][["taken_at_timestamp"]]) > 0,
        json[["node"]][["taken_at_timestamp"]],
        json[["node"]][["date"]]
      )
      
      
      is_story <- ifelse(
        length(json[["node"]][["expiring_at_timestamp"]]) > 0,
        TRUE, 
        FALSE
      )
      
      expiring_at <- ifelse(
        is_story == TRUE,
        json[["node"]][["expiring_at_timestamp"]],
        NA
      )
      
      device_timestamp <- ifelse(
        length(json[["node"]][["iphone_struct"]][["device_timestamp"]]) > 0,
        json[["node"]][["iphone_struct"]][["device_timestamp"]],
        NA
      )
      
      reel_id <- ifelse(
        length(json[["node"]][["iphone_struct"]][["highlights_info"]][["added_to"]][[1]][["reel_id"]]) > 0,
        str_remove(json[["node"]][["iphone_struct"]][["highlights_info"]][["added_to"]][[1]][["reel_id"]], "highlight:"),
        NA
      )
      
      story_link <- ifelse(
        length(json[["node"]][["iphone_struct"]][["story_link_stickers"]][[1]][["story_link"]][["display_url"]] > 0),
        json[["node"]][["iphone_struct"]][["story_link_stickers"]][[1]][["story_link"]][["display_url"]],
        NA
      )
      
      music_artist <-  ifelse(
        length(json[["node"]][["iphone_struct"]][["story_music_stickers"]][[1]][["music_asset_info"]][["display_artist"]] > 0),
        json[["node"]][["iphone_struct"]][["story_music_stickers"]][[1]][["music_asset_info"]][["display_artist"]],
        NA
      )
      
      music_song <-  ifelse(
        length(json[["node"]][["iphone_struct"]][["story_music_stickers"]][[1]][["music_asset_info"]][["title"]] > 0),
        json[["node"]][["iphone_struct"]][["story_music_stickers"]][[1]][["music_asset_info"]][["title"]],
        NA
      )
      
      tibble(path = path, 
             type = type,
             shortcode = shortcode,
             timestamp = timestamp,
             date = as.character(as_date(as_datetime(timestamp))),
             is_story = is_story,
             reel_id = reel_id,
             expiring_at = expiring_at,
             expiring_at_date = as.character(as_date(as_datetime(expiring_at))),
             #device_timestamp = device_timestamp,
             #device_timestamp_date = as_date(as_datetime(device_timestamp)),
             accessibility_caption = json[["node"]][["accessibility_caption"]],
             caption = json[["node"]][["caption"]],
             like_count = json[["node"]][["edge_media_preview_like"]][["count"]],
             comments_count = json[["node"]][["comments"]],
             location_name = json[["node"]][["location"]][["name"]],
             story_link = story_link,
             music_artist = music_artist,
             music_song = music_song
             )
      } else {
        NULL
      }
    }, .progress = T)

 if (nrow(posts_export)>0) {
#   testthat::test_that(
#     desc = "shorcode has 9 chars",
#     expect_equal(
#       posts_export %>% filter(!nchar(shortcode) %in% c(10, 11)) %>% nrow(), 0
#     )
#   )
  DBI::dbWriteTable(con, posts_tbl, posts_export  %>% anti_join(posts_in_db, by = join_by(path)), append = T)
  cli::cli_alert_success("posts_export")
}



# connections data --------------------------------------------------------

archived_accounts <- tbl(con, posts_metadata_tbl) %>%
  distinct(username) %>%
  collect() %>%
  filter(!str_detect(tolower(username), "csd|kunterbunt|queer|vida_landsberg|andreagibson"))

connections_in_db <- tbl(con, connections_tbl) %>% collect()

connections_export <- map_df(archived_accounts$username, function(this_username) {
  
  #cli::cli_alert_info("get connections for {this_username}")
  
  connections_raw <- bind_rows(
    get_tagged_users(this_username) %>% 
      mutate(
        user_in_focus = this_username, .before = 1,
        type = "tagged_by_other_user"),
    
    get_commentators(this_username) %>% 
      mutate(
        user_in_focus = this_username, .before = 1,
        type = "this_user_commented"),
    
    get_mentioned_users(this_username) %>% 
      mutate(
        user_in_focus = this_username, .before = 1,
        type = "mentioned_by_user"),
    
    get_followers(this_username) %>% 
      mutate(
        user_in_focus = this_username, .before = 1,
        type = "followers_of_user") %>% 
      distinct(user_in_focus, username, type),
    
    get_followees(this_username) %>% 
      mutate(
        user_in_focus = this_username, .before = 1,
        type = "accounts_that_user_follows") %>% 
      distinct(user_in_focus, username, type)
  ) %>% 
    filter(!is.na(username))
})


# testthat::test_that(
#   desc = "shortcode has correct nchars",
#   expect_equal(
#     connections_export %>% filter(!nchar(shortcode) %in% c(10, 11, NA), 
#                                   !str_detect(path, "comment")) %>% nrow(), 0
#   )
# )



DBI::dbWriteTable(con, connections_tbl, connections_export %>% anti_join(connections_in_db, by = join_by(user_in_focus, path, username, type, shortcode, reel_id, text)), append = T)

cli::cli_alert_success("connections_export")
new_data <- connections_export %>% anti_join(already_in_db, by = join_by(path))

DBI::dbDisconnect(con)
