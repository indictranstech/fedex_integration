## FedEx Integration with ERPNext.

Commands to install app -

```
$ bench get-app fedex_integration https://github.com/indictranstech/fedex_integration.git
$ bench install-app fedex_integration
$ bench migrate

```
Note - Due to some issues, Custom fields are not populating in correct order.So try bench migrate command multiple times (4 times). Also, It would be better to create new site & install the app it rather using production site.


This integration allows you to use Fedex web services to ship packages using ERPNext Packing Slip.

Below FedEx web Services are integrated succesfully.

1. Make Shipment.
2. Get Shipment Rate.
3. Schedule Pickup.


Steps To start using FedEx integration - 


1. User Should have FedEX Account no, FedEx Key, FedEx Meter No & Password.To generate these details, please refer below link for further details.
http://www.fedex.com/us/developer/web-services/index.html

2. Fill the above mentioned details in Shipment Forwarder master.

3. Refer FedEx Postal Code master, Please enter the postal codes where you want to ship the packages.
Ideally FedEX provides csv files for postal codes where delivery is allowed. You can import it in this master.So,our integration will only allow us to ship if given postal code is available in FedEx postal Code master.

4. Then you can create Sales order & submit it. & make draft state Delivery Note from that SO.

5. Make Packing Slip from delivery note & fill mandatory details. & on save of packing slip, FedEX rate will get fetched.

6. On submit of packing Slip,FedEx Shipment will be scheduled. You can see FedEx labels & Commercial invoice attached to attachments section of Packing Slip.

7. You can Schedule Pickup for submiited Packing Slip. 


Currently we have only tested & allowed 3 FedEx Service-types which are mainly used for domestic shipping.

1. Standard Overnight
2. Priority Overnight
3. FedEx Economy (FedEX Express Saver) 




Note - FedEx integration is done as per customer requirements.So,we have done some minor changes to to be used by other ERPNext community members.It may affect current Packing Slip functionality.


#### License

MIT