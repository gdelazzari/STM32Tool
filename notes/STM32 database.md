# Request the list of the products (with all the info) in JSON format
curl 'http://www.st.com/content/st_com/en/products/microcontrollers/stm32-32-bit-arm-cortex-mcus.product-grid.html/SC1169.json'

# Request an XLS with the specified products data
curl 'http://a={"productIds":["PF262355"],"columnIds":["1","4","3144","1901"],"superAttributesColumnIds":[]}&:cq_csrf_token=undefined'

