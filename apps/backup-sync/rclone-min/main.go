package main

import (
	_ "github.com/rclone/rclone/backend/local"
	_ "github.com/rclone/rclone/backend/s3"
	"github.com/rclone/rclone/cmd"
	_ "github.com/rclone/rclone/cmd/copy"
	_ "github.com/rclone/rclone/cmd/copyto"
	_ "github.com/rclone/rclone/cmd/lsf"
	_ "github.com/rclone/rclone/cmd/sync"
	_ "github.com/rclone/rclone/cmd/version"
)

func main() {
	cmd.Main()
}
