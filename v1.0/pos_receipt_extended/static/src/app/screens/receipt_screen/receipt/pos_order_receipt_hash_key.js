/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(OrderReceipt.prototype, {
      setup(){
      super.setup();
        this.orm = useService("orm");
    },
     async getTempHash() {
        const response = await this.orm.call("pos.order", "get_hash_key", [
            this.props.data.name,
        ]);
        const concate = response.charAt(0) + response.charAt(10) +  response.charAt(20) + response.charAt(30);
        this.props.data.hashdata = concate;
        $('#hash_key').text(concate)
        console.log('response123',response)
    },
  });
