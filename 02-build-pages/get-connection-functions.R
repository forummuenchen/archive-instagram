get_followers <- function(this_username) {
  followers <- tbl(con, "followers") %>%
    filter(profile == this_username) %>%
    select(follower) %>%
    left_join(
      tbl(con, "profiles_from_apify") %>%
        select(username, full_name, biography, followers_count, private, is_business_account),
      by = join_by(follower == username)
    ) %>%
    collect() %>%
    rename(username = follower)
  
  if (nrow(followers) == 0) {
    followers <- tibble(
      username = NA_character_,
      full_name = NA_character_,
      biography = NA_character_,
      followers_count = NA_character_,
      private = NA_character_,
      is_business_account = NA_character_
    ) %>%
      filter(!is.na(username))
  }
  
  followers
}


get_followees <- function(this_username) {
  followees <- tbl(con, "followees") %>%
    filter(profile == this_username) %>%
    select(followee) %>%
    left_join(
      tbl(con, "profiles_from_apify") %>%
        select(username, full_name, biography, followers_count, private, is_business_account),
      by = join_by(followee == username)
    ) %>%
    collect() %>%
    rename(username = followee)
  if (nrow(followees) == 0) {
    followers <- tibble(
      username = NA_character_,
      full_name = NA_character_,
      biography = NA_character_,
      followers_count = NA_character_,
      private = NA_character_,
      is_business_account = NA_character_
    ) %>%
      filter(!is.na(username))
  }
  followees
}




get_mentioned_users <- function(this_username, posts_db_tbl = posts_tbl, verbose = F) {
  file_ext_regex <- "json.xz"
  year_regex <- "20[0-9]{2}"
  
  files <- fs::dir_ls(here::here(glue("data/{this_username}")), type = "file", regexp = file_ext_regex, recurse = T)
  
  mentioned_users_raw <- map_df(files, function(this_file) {
    if (verbose == T) {
      cli::cli_alert_info("{this_file}")
    }
    
    
    # this_file <- "/Users/kabrbr/code/rechte-by-instagram/data/089.jakob/089.jakob_16470531674.json.xz"
    json <- jsonlite::read_json(here::here(this_file))
    reel_mention_node <- json$node$iphone_struct$reel_mentions
    
    if (!is.null(reel_mention_node) == T) {
      mentioned_users_tmp <- reel_mention_node %>%
        rrapply::rrapply(how = "melt") %>%
        as_tibble() %>%
        filter(L3 == "username") %>%
        distinct(value) %>%
        rename(username = value)
    } else {
      mentioned_users_tmp <- NULL
    }
    
    tibble(path = str_remove(str_remove(this_file, "Users/kabrbr/code/rechte-by-instagram/"), "^/"), mentioned_users_tmp)
  })
  
  if (ncol(mentioned_users_raw) > 1) {
    mentioned_users_raw <- mentioned_users_raw %>%
      filter(username != "")
    mentioned_users_raw
    
    input_path <- unique(mentioned_users_raw$path)
    
    post_metadata <- tbl(con, posts_tbl) %>%
      select(path, type, shortcode, reel_id) %>%
      filter(path %in% input_path) %>%
      collect()
    
    
    mentioned_users <- mentioned_users_raw %>%
      left_join(post_metadata, by = join_by(path))
    mentioned_users
  } else {
    tibble(
      path = NA_character_,
      username = NA_character_,
      type = NA_character_,
      shortcode = NA_character_,
      reel_id = NA_character_
    ) %>%
      filter(!is.na(path))
  }
}
get_tagged_users <- function(this_username, posts_db_tbl = posts_tbl, verbose = F) {
  file_ext_regex <- "json.xz"
  year_regex <- "20[0-9]{2}"
  
  files <- fs::dir_ls(here::here(glue("data/{this_username}")), type = "file", regexp = file_ext_regex, recurse = T)
  
  
  tagged_users_raw <- map_df(files, function(this_file) {
    # verbose <- T
    # this_file <- "/Users/kabrbr/code/rechte-by-instagram/data/aufkakeausgerutscht/2025/DK-AdJLsOlB_2025-06-16_16-45-32_UTC.json.xz"
    if (verbose == T) {
      cli::cli_alert_info("{this_file}")
    }
    
    json <- jsonlite::read_json(here::here(this_file))
    tagged_users_node <- json[["node"]][["edge_media_to_tagged_user"]][["edges"]]
    
    if (!is.null(tagged_users_node) == T && length(tagged_users_node) > 0) {
      tagged_users_tmp <- tagged_users_node %>%
        rrapply::rrapply(how = "melt") %>%
        as_tibble() %>%
        filter(L4 == "username") %>%
        distinct(value) %>%
        rename(username = value)
    } else {
      tagged_users_tmp <- NULL
    }
    
    tibble(path = str_remove(str_remove(this_file, "Users/kabrbr/code/rechte-by-instagram/"), "^/"), tagged_users_tmp)
  })
  
  if (ncol(tagged_users_raw) > 1) {
    tagged_users_raw <- tagged_users_raw %>%
      filter(username != "")
    input_path <- unique(tagged_users_raw$path)
    
    post_metadata <- tbl(con, posts_tbl) %>%
      select(path, type, shortcode, reel_id) %>%
      filter(path %in% input_path) %>%
      collect()
    
    
    tagged_users <- tagged_users_raw %>%
      left_join(post_metadata, by = join_by(path))
    tagged_users
  } else {
    tagged_users <- tibble(
      path = NA_character_,
      username = NA_character_,
      type = NA_character_,
      shortcode = NA_character_,
      reel_id = NA_character_
    ) %>%
      filter(!is.na(path))
  }
}


get_commentators <- function(this_username, verbose = F) {
  if (verbose == T) {
    cli::cli_alert_info("{this_username}")
  }
  
  
  file_ext_regex <- "json.xz"
  year_regex <- "20[0-9]{2}"
  
  files_comments <- fs::dir_ls(here::here(glue("data/{this_username}")), type = "file", regexp = "comment", recurse = T)
  
  if (length(files_comments) > 0) {
    commentators <- map_df(files_comments, function(this_file) {
      if (verbose == T) {
        cli::cli_alert_info("{this_file}")
      }
      
      
      json <- jsonlite::read_json(here::here(this_file))
      
      comments_tmp <- json %>%
        rrapply::rrapply(how = "melt") %>%
        as_tibble() %>%
        filter(L3 == "username" | L2 == "text") %>%
        mutate(L3 = case_when(
          is.na(L3) ~ "text",
          TRUE ~ L3
        )) %>%
        pivot_wider(id_cols = L1, names_from = L3, values_from = value)
      
      commentators_raw <- tibble(path = this_file, comments_tmp) %>%
        mutate(
          path = str_remove(path, "/Users/kabrbr/code/rechte-by-instagram/"),
          shortcode = str_remove(str_extract(path, ".*_20"), "_20"), 
          shortcode = str_sub(shortcode, 1, 11)
          #shortcode = str_extract(path, glue("{year_regex}.*")) %>% str_remove(., glue("{year_regex}/")) %>% str_extract(., "^[^_]+")
        ) %>%
        select(path, shortcode, username, text)
    })
  } else {
    commentators <- tibble(
      path = NA_character_,
      shortcode = NA_character_,
      username = NA_character_,
      text = NA_character_
    ) %>%
      filter(!is.na(file))
  }
  
  commentators
}
