docker run --name food_ordering_mysql \
  -e MYSQL_ROOT_PASSWORD=root_password \
  -e MYSQL_DATABASE=food_ordering_db \
  -e MYSQL_USER=admin \
  -e MYSQL_PASSWORD=asdfghjkl \
  -p 3306:3306 \
  -d mysql:8.0