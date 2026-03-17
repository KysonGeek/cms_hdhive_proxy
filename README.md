# cms_hdhive_proxy
解决nuller失联导致cms增强插件失效问题，代码都是AI写的，可以直接看prompt

**使用步骤**
1. 拉取代码到本地 & 配置hdhive token
```
git clone https://github.com/KysonGeek/cms_hdhive_proxy.git
cd cms_hdhive_proxy
cat <<EOF > .env
HDHIVE_TOKEN=xxx
EOF
```
2. 启动服务
```
python3 -m venv venv
source venv
pip install -r requirements.txt
nohup python3 -u main.py > output.log 2>&1 &
```
查看output.log是否启动成功

3. caddy拦截请求
```
cms.xxx.xx {
    # 拦截接口1: 查询影片资源信息
    @movie_resources {
        method GET
        path_regexp movie_res ^/api/nullbr/(tv|movie)/(\d+)/resources$
    }
    handle @movie_resources {
        reverse_proxy localhost:8900
    }

    # 拦截接口2: 获取115链接列表
    @movie_115 {
        method GET
        path_regexp movie_115 ^/api/nullbr/(tv|movie)/(\d+)/115$
    }
    handle @movie_115 {
        reverse_proxy localhost:8900
    }

    # 拦截接口3: 转存接口
    @cloud_add {
        method POST
        path /api/cloud/add_share_down
    }
    handle @cloud_add {
        reverse_proxy localhost:8900
    }

    # 其他请求照常转发到原始后端
    handle {
        reverse_proxy 127.0.0.1:9527
    }
}
```
systemctl restart caddy重新加载配置

**prompt**
```
url1（get）:https://cms.qixin.ch/api/nullbr/movie/1265609/resources
返回值：
{
    "code": 200,
    "data": {
        "movie_info": {
            "id": 755898,
            "title": "世界大战",
            "poster": "https://image.tmdb.org/t/p/w154//yvirUYrva23IudARHn3mMGVxWqM.jpg",
            "overview": "威尔·拉德福德是国土安全部的顶级网络安全分析师，他通过大规模监控项目追踪国家安全的潜在威胁。直到有一天，一个不明实体的攻击让他开始怀疑政府是否对他……以及世界其他地方隐瞒了什么。",
            "vote": 4.518,
            "release_date": "2025-07-29"
        },
        "available_resources": {
            "has_115": true,
            "has_magnet": true,
            "has_ed2k": true,
            "has_video": true
        }
    }
}

url2(get)https://cms.qixin.ch/api/nullbr/movie/1265609/115
返回值：
{
    "code": 200,
    "data": {
        "tmdbid": 1265609,
        "page": 1,
        "total_page": 1,
        "resources": [
            {
                "title": "War Machine (2026) {tmdbid-1265609}",
                "size": "4.31 GB",
                "share_link": "https://115cdn.com/s/swfvq8f36gr?password=cc2v&#",
                "resolution": "1080p",
                "quality": null,
                "season_list": null
            },
            {
                "title": "War Machine (2026) {tmdbid-1265609}",
                "size": "14.9 GB",
                "share_link": "https://115cdn.com/s/swfv8oh36gr?password=cc2v&#",
                "resolution": "2160p",
                "quality": "Dolby Vision",
                "season_list": null
            }
        ]
    }
}

url3(post)https://cms.qixin.ch/api/cloud/add_share_down
请求体
{"url":"https://115cdn.com/s/swfvq8f36gr?password=cc2v&#"}



我的vps上部署了一个服务，其中包含了上面3个接口：
1. 查询影片
2. 获取115链接列表
3. 转存
但是这三个接口中前两个接口依赖的第三方出现了问题，需要用caddy拦截后，请求一个python服务（采用其他三方服务），由于新的第三方需要先解锁再在转存
新的第三方服务接口如下
url11（get）https://hdhive.com/api/open/resources/tv/101172
返回值：
{
    "success": true,
    "data": [
        {
            "slug": "74366deefd1544c1905ab0f58ee4c9f8",
            "title": "吞噬星空 (2020)",
            "pan_type": "115",
            "media_url": "https://hdhive.com/tv/44267f43fbd611edb16e0242c0a81003",
            "media_slug": "44267f43fbd611edb16e0242c0a81003",
            "share_size": "228.75",
            "video_resolution": [
                "4K"
            ],
            "source": [
                "WEB-DL/WEBRip"
            ],
            "subtitle_language": [
                "简中"
            ],
            "subtitle_type": [],
            "remark": "已整理命名，S01E01-E215，持续更新",
            "unlock_points": 6,
            "unlocked_users_count": 15,
            "validate_status": null,
            "validate_message": null,
            "last_validated_at": null,
            "is_official": false,
            "is_unlocked": false,
            "user": {
                "id": 54697,
                "nickname": "开心超人",
                "avatar_url": "https://t.me/i/userpic/320/lv442R3QBGMVKB3G6JWNDiXL0-2ygBnpwG8L8tE1-zE.jpg"
            },
            "created_at": "2026-03-12 17:40:15"
        },
        {
            "slug": "41f71882302145bbb51b2400c8b834e8",
            "title": "吞噬星空 (2020)",
            "pan_type": "115",
            "media_url": "https://hdhive.com/tv/44267f43fbd611edb16e0242c0a81003",
            "media_slug": "44267f43fbd611edb16e0242c0a81003",
            "share_size": "1.07g",
            "video_resolution": [
                "4K"
            ],
            "source": [
                "WEB-DL/WEBRip"
            ],
            "subtitle_language": [
                "简中"
            ],
            "subtitle_type": [
                "内嵌"
            ],
            "remark": "吞噬星空E211\nSwallowed.Star.S01E211.2020.2160p.WEB-DL.H265.AAC",
            "unlock_points": 2,
            "unlocked_users_count": 10,
            "validate_status": null,
            "validate_message": null,
            "last_validated_at": null,
            "is_official": false,
            "is_unlocked": false,
            "user": {
                "id": 47494,
                "nickname": "Shrom ",
                "avatar_url": ""
            },
            "created_at": "2026-02-16 20:41:26"
        }
    ],
    "meta": {
        "total": 41
    },
    "message": "success",
    "code": "200"
}
与url1返回值的参数对应
data.movie_info.title == data[0].title

与url2返回值的参数对应
data.resources[].title == data[].title
data.resources[].size == data[].share_size
data.resources[].share_link == data[].slug
data.resources[].resolution == data[].video_resolution

新第三方服务的接口
url33(post) https://hdhive.com/api/open/resources/unlock
参数：
{"slug": "c68ce9afa88b11ef87c60242ac120005"}
返回值：
{
    "success": true,
    "data": {
        "url": "https://115.com/s/swh7gxg3hy1?password=kd19# 吞噬星空 访问码：kd19 复制这段内容，可在115App中直接打开！",
        "access_code": "",
        "full_url": "https://115.com/s/swh7gxg3hy1?password=kd19# 吞噬星空 访问码：kd19 复制这段内容，可在115App中直接打开！",
        "already_owned": false
    },
    "message": "免费资源",
    "code": "200"
}

拿到返回值后，调用url3（使用localhost调用跳过域名拦截）

需要你写一个caddy配置拦截最开始的三个接口，然后写一个python服务，拦截后的请求转发到python服务

```

